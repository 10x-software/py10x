from __future__ import annotations

import pytest
import uuid6
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
    s_mongo_running = True
    s_postgres_running = True

    def _mongo_store(self) -> TsStore | None:
        if self.s_mongo_running:
            try:
                return MongoStore.instance(hostname='mongodb://localhost:27017/', dbname=f'copy_to_{uuid6.uuid7().hex}', sst=100)
            except Exception:  # noqa: BLE001
                self.s_mongo_running = False
        need(self.s_mongo_running, 'MongoDB running (copy_to tests)')
        return None

    def _postgres_store(self) -> PostgresStore | None:
        if self.s_postgres_running:
            uri = TEST_TS_STORE.POSTGRES.value[0]
            if not TsStore.is_running_with_auth_from_uri(uri)[0]:
                self.s_postgres_running = False
            else:
                try:
                    store = TsStore.instance_from_uri(uri, _cache=False)
                    assert isinstance(store, PostgresStore)
                    return store
                except Exception:  # noqa: BLE001
                    self.s_postgres_running = False
        need(self.s_postgres_running, 'PostgreSQL running (copy_to tests)')
        return None

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
    def mongo_src(self):
        store = self._mongo_store()
        name = f'mcopy_{uuid6.uuid7().hex}'
        coll = store.collection(name, {})  # Mongo ignores trait_dir
        coll.save_new({'_id': 'm1', 'x': 1})
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

    def test_ibis_empty_table_empty_intrinsic_trait_dir_raises(self):
        store = DuckDbStore()
        store.begin_using()
        name = f'empty_{uuid6.uuid7().hex}'
        # Register handle + empty shell (no payload columns → empty intrinsic_trait_dir).
        store.collection(name, {})
        store.ensure_table(name)
        dst = DuckDbStore()
        dst.begin_using()
        try:
            with pytest.raises(TsCopyError, match='intrinsic_trait_dir'):
                store.copy_to(dst)
        finally:
            store.delete_collection(name)
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

    def test_ibis_to_mongo(self, duck_src):
        src, name = duck_src
        dst = self._mongo_store()
        try:
            rc = src.copy_to(dst)
            assert rc
            to_coll = dst.collection(name, {})  # Mongo ignores trait_dir
            assert to_coll.count() == 2
            assert to_coll.load('a')['age'] == 30
        finally:
            dst.delete_collection(name)

    def test_mongo_to_mongo(self, mongo_src):
        src, name = mongo_src
        dst = self._mongo_store()
        try:
            rc = src.copy_to(dst)
            assert rc
            to_coll = dst.collection(name, {})
            assert to_coll.load('m1')['x'] == 1
        finally:
            dst.delete_collection(name)

    def test_duck_to_postgres(self, duck_src):
        src, name = duck_src
        dst = self._postgres_store()
        try:
            rc = src.copy_to(dst)
            assert rc
            to_coll = dst.collection(name, CopyPerson.s_dir)
            assert to_coll.count() == 2
            doc = to_coll.load('a')
            assert doc['name'] == 'Ann' and doc['age'] == 30
        finally:
            dst.delete_collection(name)

    def test_postgres_to_postgres(self):
        """Collection-level copy (shared ``postgres`` DB — avoid store-wide copy_to)."""
        store = self._postgres_store()
        src_name = f'pgcopy_src_{uuid6.uuid7().hex}'
        dst_name = f'pgcopy_dst_{uuid6.uuid7().hex}'
        from_coll = store.collection(src_name, CopyPerson.s_dir)
        from_coll.save_new({'_id': 'a', 'name': 'Ann', 'age': 30})
        from_coll.save_new({'_id': 'b', 'name': 'Bob', 'age': 40})
        to_coll = store.collection(dst_name, CopyPerson.s_dir)
        try:
            rc = from_coll.copy_to(to_coll)
            assert rc
            assert to_coll.count() == 2
            assert to_coll.load('a')['age'] == 30
        finally:
            store.delete_collection(src_name)
            store.delete_collection(dst_name)
