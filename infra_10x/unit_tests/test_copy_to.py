from __future__ import annotations

import pytest
import uuid6
from core_10x.testlib import test_databases
from core_10x.testlib.strict import need
from core_10x.trait_definition import T
from core_10x.traitable import Traitable
from core_10x.ts_store import TsCopyError, TsStore
from infra_10x.duckdb_store import DuckDbStore
from infra_10x.ibis_store import _DATA, _ID, _REV
from infra_10x.mongodb_store import MongoStore
from infra_10x.postgres_store import PostgresStore
from infra_10x.unit_tests.conftest import TEST_TS_STORE


class CopyPerson(Traitable, custom_collection=True):
    name: str = T(T.ID)
    age: int = T()


class TestCopyTo:
    @pytest.fixture
    def postgres_store(self, live_store) -> TsStore:
        need(store := live_store(TEST_TS_STORE.POSTGRESQL.name), 'PostgreSQL running (copy_to tests)')
        return store

    @pytest.fixture
    def mongo_store(self, live_store) -> TsStore:
        need(store := live_store(TEST_TS_STORE.MONGODB.name), 'MongoDB running (copy_to tests)')
        return store

    @pytest.fixture
    def duck_src(self):
        store = DuckDbStore()
        store.begin_using()
        name = f'copy_src_{uuid6.uuid7().hex}'
        coll = store.collection(name, CopyPerson.s_dir)
        coll.save_new({'_id': 'a', 'name': 'Ann', 'age': 30})
        coll.save_new({'_id': 'b', 'name': 'Bob', 'age': 40})
        yield store, name
        store.delete_collection(name)
        store.end_using()

    @pytest.fixture
    def mongo_src(self, live_store):
        need(
            store := live_store(TEST_TS_STORE.MONGODB.name, f'{test_databases.TEST_DB_PREFIX}_copy_src_{uuid6.uuid7().hex[:8]}'),
            'MongoDB running (copy_to tests)',
        )
        name = f'mcopy_{uuid6.uuid7().hex}'
        coll = store.collection(name, {})  # Mongo ignores trait_dir
        coll.save_new({'_id': 'm1', 'x': 1})
        yield store, name
        store.delete_collection(name)

    @pytest.fixture
    def postgres_src(self, live_store):
        """Postgres source on its **own** database, so a store-wide copy has a distinct target."""
        need(
            store := live_store(TEST_TS_STORE.POSTGRESQL.name, f'{test_databases.TEST_DB_PREFIX}_copy_src_{uuid6.uuid7().hex[:8]}'),
            'PostgreSQL running (copy_to tests)',
        )
        name = f'pgcopy_{uuid6.uuid7().hex}'
        coll = store.collection(name, CopyPerson.s_dir)
        coll.save_new({'_id': 'a', 'name': 'Ann', 'age': 30})
        coll.save_new({'_id': 'b', 'name': 'Bob', 'age': 40})
        yield store, name
        store.delete_collection(name)

    def test_ibis_to_ibis_round_trip(self, duck_src):
        src, name = duck_src
        dst = DuckDbStore()
        dst.begin_using()
        try:
            rc = src.copy_to(dst)
            assert rc
            to_coll = dst.collection(name, CopyPerson.s_dir)
            assert to_coll.count() == 2
            doc = to_coll.load('a')
            assert doc['name'] == 'Ann' and doc['age'] == 30
            cols = dst._collection_columns(name)
            assert 'age' in cols and 'name' in cols
        finally:
            dst.delete_collection(name)
            dst.end_using()

    def test_blob_only_collection_round_trip(self):
        """A collection with no promoted columns copies: ``intrinsic_trait_dir()`` is ``{}``.

        ``{}`` means "schema declared, nothing column-eligible" (writable blob-only), unlike
        ``None`` which means "no schema" (read-only). Conflating the two used to abort the
        whole store-wide copy on the first such collection.
        """

        class Blobby(Traitable, custom_collection=True, keep_history=False):
            tags: list = T()  # -- non-scalar wire type: never promoted to an SQL column

        src, dst = DuckDbStore(), DuckDbStore()
        name = f'blobonly_{uuid6.uuid7().hex}'
        src.collection(name, Blobby.s_dir).save_new({'_id': 'a', 'tags': [1, 2]})
        try:
            assert src.collection(name, {}).intrinsic_trait_dir() == {}
            assert src.copy_to(dst)
            assert dst.collection(name, {}).load('a')['tags'] == [1, 2]
        finally:
            src.delete_collection(name)
            dst.delete_collection(name)

    def test_intrinsic_trait_dir(self, duck_src):
        src, name = duck_src
        del src._collections[name]
        from_coll = src.collection(name, {})
        assert from_coll.col_trait_dir == {}
        assert 'age' in from_coll.intrinsic_trait_dir()

    def test_ibis_to_ibis_copies_extra_sql_columns(self, duck_src):
        src, name = duck_src
        safe = name.replace('"', '""')
        src._con.execute(f'ALTER TABLE "{safe}" ADD COLUMN IF NOT EXISTS "legacy" VARCHAR')
        src._con.execute(
            f'INSERT INTO "{safe}" ({_ID}, {_REV}, _data, name, age, legacy) VALUES (?, 1, ?, ?, ?, ?)',
            ['c', '{}', 'Cal', 50, 'old'],
        )

        dst = DuckDbStore()
        dst.begin_using()
        try:
            rc = src.copy_to(dst)
            assert rc
            to_coll = dst.collection(name, {})
            assert to_coll.load('c')['legacy'] == 'old'
        finally:
            dst.delete_collection(name)
            dst.end_using()

    def test_ibis_empty_table_empty_intrinsic_trait_dir_copies(self):
        """An empty shell (no payload columns) copies to an empty shell, it does not raise.

        Previously an empty ``intrinsic_trait_dir()`` aborted the whole store-wide copy; it
        just means blob-only — see ``test_blob_only_collection_round_trip``.
        """
        store = DuckDbStore()
        store.begin_using()
        name = f'empty_{uuid6.uuid7().hex}'
        # Register handle + empty shell (no payload columns → empty intrinsic_trait_dir).
        store.collection(name, {})
        store.ensure_table(name)
        dst = DuckDbStore()
        dst.begin_using()
        try:
            assert store.copy_to(dst)
            assert dst.collection(name, {}).count() == 0
            # Nothing was written, so lazy DDL never materialized the target table
            # (same rule as test_ibis_open_without_write_not_in_collection_names).
            assert dst.collection_names() == []
        finally:
            store.delete_collection(name)
            dst.delete_collection(name)
            dst.end_using()
            store.end_using()

    def test_ibis_open_without_write_not_in_collection_names(self):
        store = DuckDbStore()
        store.begin_using()
        name = f'lazy_{uuid6.uuid7().hex}'
        store.collection(name, {})
        assert name not in store.collection_names()
        store.end_using()

    def test_delete_collection_without_cached_handle(self):
        """Physical table must be droppable even if never opened into ``_collections``."""
        store = DuckDbStore()
        store.begin_using()
        name = f'uncached_{uuid6.uuid7().hex}'
        store._create_table_if_not_exists(name)
        assert store._collection_columns(name)
        assert name not in store._collections
        assert store.delete_collection(name) is True
        assert not store._collection_columns(name)
        store.end_using()

    def test_mongo_to_ibis_raises(self, mongo_src):
        src, _name = mongo_src
        dst = DuckDbStore()
        with pytest.raises(TsCopyError, match='Cannot copy from MongoStore'):
            src.copy_to(dst)

    def test_ibis_to_mongo(self, duck_src, mongo_store):
        src, name = duck_src
        dst = mongo_store
        try:
            rc = src.copy_to(dst)
            assert rc
            to_coll = dst.collection(name, {})  # Mongo ignores trait_dir
            assert to_coll.count() == 2
            assert to_coll.load('a')['age'] == 30
        finally:
            dst.delete_collection(name)

    def test_mongo_to_mongo(self, mongo_src, mongo_store):
        """Store-wide schemaless -> schemaless: the only case of that in the copy_to matrix.

        Hence a second database for the source, unlike ``test_postgres_to_postgres`` which is
        collection-level because both sides share this session's one database.
        """
        src, name = mongo_src
        dst = mongo_store
        try:
            rc = src.copy_to(dst)
            assert rc
            to_coll = dst.collection(name, {})
            assert to_coll.load('m1')['x'] == 1
        finally:
            dst.delete_collection(name)

    def test_duck_to_postgres(self, duck_src, postgres_store):
        src, name = duck_src
        dst = postgres_store
        try:
            rc = src.copy_to(dst)
            assert rc
            to_coll = dst.collection(name, CopyPerson.s_dir)
            assert to_coll.count() == 2
            doc = to_coll.load('a')
            assert doc['name'] == 'Ann' and doc['age'] == 30
        finally:
            dst.delete_collection(name)

    def test_postgres_to_postgres(self, postgres_src, postgres_store):
        """Store-wide schema -> schema across two Postgres databases (mirrors test_mongo_to_mongo)."""
        src, name = postgres_src
        dst = postgres_store
        try:
            assert src.copy_to(dst)
            to_coll = dst.collection(name, CopyPerson.s_dir)
            assert to_coll.count() == 2
            assert to_coll.load('a')['age'] == 30
        finally:
            dst.delete_collection(name)

    def test_collection_to_collection(self):
        """``TsCollection.copy_to`` called directly — store-wide copy only reaches it internally."""
        store = DuckDbStore()
        src_name, dst_name = f'ccopy_src_{uuid6.uuid7().hex}', f'ccopy_dst_{uuid6.uuid7().hex}'
        from_coll = store.collection(src_name, CopyPerson.s_dir)
        from_coll.save_new({'_id': 'a', 'name': 'Ann', 'age': 30})
        from_coll.save_new({'_id': 'b', 'name': 'Bob', 'age': 40})
        to_coll = store.collection(dst_name, CopyPerson.s_dir)
        assert from_coll.copy_to(to_coll)
        assert to_coll.count() == 2
        assert to_coll.load('a')['age'] == 30
