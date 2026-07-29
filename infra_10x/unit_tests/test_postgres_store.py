"""PostgreSQL-specific dialect tests (shared suites run via conftest ts_instance matrix)."""

from __future__ import annotations

import os
from datetime import datetime  # noqa: TC003  # used as runtime trait data_type

import pytest

from core_10x.trait_definition import T
from core_10x.traitable import Traitable
from core_10x.ts_store import TsDuplicateKeyError, TsStore
from core_10x.ts_store_type import TS_STORE_TYPE
from infra_10x.ibis_store import _DATA, _ID
from infra_10x.postgres_store import PostgresStore
from infra_10x.unit_tests.conftest import TEST_TS_STORE


def test_postgresql_parse_uri_and_registry():
    assert TS_STORE_TYPE.ts_store_class('postgresql') is PostgresStore
    uri = 'postgresql://user:pass@localhost:5432/testdb'
    args = PostgresStore.parse_uri(uri)
    assert args[PostgresStore.HOSTNAME_TAG] == 'localhost'
    assert args[PostgresStore.DBNAME_TAG] == 'testdb'
    assert args[PostgresStore.USERNAME_TAG] == 'user'
    assert args[PostgresStore.PASSWORD_TAG] == 'pass'
    assert args[PostgresStore.PORT_TAG] == 5432
    spec = PostgresStore.spec_from_uri(uri)
    assert spec.kwargs.get(PostgresStore.PROTOCOL_TAG) == 'postgresql'
    # TEST_TS_STORE.POSTGRES is the same URI used by the shared suite fixture.
    uri, helpers, hard = TEST_TS_STORE.POSTGRES.value
    assert uri.startswith('postgresql://')
    assert helpers == (False,)
    assert hard == False


def test_auth_user_is_server_session_user(postgres_store):
    """TS_USER identity is current_user, not Resource.username (unlike Mongo/DuckDB)."""
    store = postgres_store
    session_user = store._execute('SELECT current_user')[0][0]
    assert store.auth_user() == session_user
    store.username = 'not_the_db_role'
    assert store.auth_user() == session_user
    assert store.auth_user() != 'not_the_db_role'


def test_ts_user_stamped_from_current_user(postgres_store, monkeypatch):
    class Ev(Traitable, custom_collection=True, keep_history=False):
        name: str = T(T.ID)
        _at: datetime = T(T.TS_TIME)
        _who: str = T(T.TS_USER)

    store = postgres_store
    coll_name = f'pg_ts_{id(store)}_{os.getpid()}'
    coll = store.collection(coll_name, Ev.s_dir)
    body = store.add_ts('_at', T.TS_TIME, {'_id': '1', 'name': 'a'})
    body = store.add_ts('_who', T.TS_USER, body)

    server_time_calls = []
    orig = type(store).server_time
    monkeypatch.setattr(type(store), 'server_time', lambda self: (server_time_calls.append(1), orig(self))[1])

    result = coll.save_new(body)
    assert not server_time_calls, 'TS_TIME must be stamped by SQL, not Python server_time()'
    assert result['_who'] == store.auth_user()
    assert result['_at'] is not None

    phys = store._physical_table_name(coll_name)
    row = store._execute(f'SELECT "_who", {_DATA} FROM "{phys}" WHERE {_ID} = ?', ['1'])[0]
    assert row[0] == store.auth_user()
    store.delete_collection(coll_name)


def test_duplicate_key_raises(postgres_store):
    class Pad(Traitable, custom_collection=True, keep_history=False):
        pad: int = T()

    store = postgres_store
    coll_name = f'pg_dup_{os.getpid()}'
    coll = store.collection(coll_name, Pad.s_dir)
    coll.save_new({'_id': 'x', 'pad': 1})
    with pytest.raises(TsDuplicateKeyError):
        coll.save_new({'_id': 'x', 'pad': 2})
    store.delete_collection(coll_name)


def test_data_column_is_jsonb(postgres_store):
    class Pad(Traitable, custom_collection=True, keep_history=False):
        pad: int = T()

    store = postgres_store
    coll_name = f'pg_jsonb_{os.getpid()}'
    coll = store.collection(coll_name, Pad.s_dir)
    coll.save_new({'_id': 'j', 'pad': 0, 'extra': 'blob'})
    phys = store._physical_table_name(coll_name)
    rows = store._execute(
        'SELECT data_type FROM information_schema.columns '
        'WHERE table_name = ? AND column_name = ?',
        [phys, _DATA],
    )
    assert rows and rows[0][0] == 'jsonb'
    store.delete_collection(coll_name)


def test_long_collection_names_do_not_collide_with_history(postgres_store):
    """PG 63-byte identifier limit must not merge main and #history into one table."""
    long_base = 'core_10x/testlib/ts_tests/Person#' + 'a' * 40
    assert len(long_base.encode()) > 63
    hist = long_base + '#history'
    store = postgres_store
    assert store._physical_table_name(long_base) != store._physical_table_name(hist)
    store.ensure_table(long_base)
    store.ensure_table(hist)
    assert store._collection_columns(long_base)
    assert store._collection_columns(hist)
    store.delete_collection(long_base)
    store.delete_collection(hist)


def test_instance_from_uri(postgres_store):
    uri = TEST_TS_STORE.POSTGRES.value[0]
    store = TsStore.instance_from_uri(uri, _cache=False)
    assert isinstance(store, PostgresStore)
    assert store.auth_user() is not None
