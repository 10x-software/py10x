"""PostgreSQL-specific dialect tests (shared suites run via conftest ts_instance matrix)."""

from __future__ import annotations

import getpass
import os
import socket
import struct
from datetime import datetime  # noqa: TC003  # used as runtime trait data_type

import pytest
from core_10x.trait_definition import T
from core_10x.traitable import Traitable
from core_10x.ts_store import TsDuplicateKeyError, TsStore
from core_10x.ts_store_type import TS_STORE_TYPE
from infra_10x.ibis_store import _DATA, _ID
from infra_10x.postgres_store import _PG_AUTH_OK, PostgresStore
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
    # Userinfo optional — omitted username stays None (libpq supplies OS user at connect).
    no_user = PostgresStore.parse_uri('postgresql://localhost:5432/postgres')
    assert no_user[PostgresStore.USERNAME_TAG] is None
    assert no_user[PostgresStore.HOSTNAME_TAG] == 'localhost'
    assert no_user[PostgresStore.DBNAME_TAG] == 'postgres'
    with_user = PostgresStore.parse_uri('postgresql://alice@localhost:5432/postgres')
    assert with_user[PostgresStore.USERNAME_TAG] == 'alice'
    # TEST_TS_STORE.POSTGRES is the same URI used by the shared suite fixture.
    uri, helpers, hard = TEST_TS_STORE.POSTGRES.value
    assert uri == 'postgresql://localhost:5432/postgres'
    assert helpers == (False,)
    assert not hard


def _short_lived_postgres(uri: str) -> PostgresStore:
    """Connect outside the session fixture without caching in ``s_instances``."""
    store = TsStore.instance_from_uri(uri, _cache=False)
    assert isinstance(store, PostgresStore)
    return store


def test_passwordless_connect_userless_uri_uses_os_user(postgres_store):
    """URI without userinfo: Resource.username is None; server role is the OS user."""
    uri = TEST_TS_STORE.POSTGRES.value[0]
    store = _short_lived_postgres(uri)
    assert store.username is None
    current = store._execute('SELECT current_user')[0][0]
    assert current == getpass.getuser()


def test_passwordless_connect_explicit_user_matches_server(postgres_store):
    """URI with OS user@: Resource.username and current_user both equal that user."""
    os_user = getpass.getuser()
    uri = f'postgresql://{os_user}@localhost:5432/postgres'
    store = _short_lived_postgres(uri)
    assert store.username == os_user
    current = store._execute('SELECT current_user')[0][0]
    assert current == store.username


def test_is_running_with_auth_unreachable_host_port():
    """TCP cannot connect → (False, False) only."""
    assert PostgresStore.is_running_with_auth('127.0.0.1', 59999) == (False, False)


def test_is_running_with_auth_non_postgres_service_on_port():
    """Something on the port that is not a successful open PG login → not (True, False).

    Mongo on 27017 (if up) fails the PG handshake after TCP; if nothing listens, TCP fails.
    Either way we must not report open access. Prefer (False, False) or (True, True).
    """
    result = PostgresStore.is_running_with_auth('127.0.0.1', 27017)
    assert result in ((False, False), (True, True))
    assert result != (True, False)


def test_is_running_with_auth_local_trust_no_password(postgres_store):
    """Passwordless ReadyForQuery (local trust / OS user) → (True, False)."""
    uri = TEST_TS_STORE.POSTGRES.value[0]
    spec = TsStore.spec_from_uri(uri)
    assert PostgresStore.is_running_with_auth(spec.hostname(), spec.port()) == (True, False)


def test_is_running_with_auth_unknown_role_try_vault(postgres_store):
    """Unknown role: ErrorResponse after handshake → (True, True) so vault is tried."""
    uri = TEST_TS_STORE.POSTGRES.value[0]
    spec = TsStore.spec_from_uri(uri)
    host, port = spec.hostname(), int(spec.port())
    dbname = PostgresStore.s_instance_kwargs_map[PostgresStore.DBNAME_TAG][1]
    sock = socket.create_connection((host, port), timeout=3.0)
    assert PostgresStore._startup_auth_probe(sock, host=host, user='no_such_pg_role_zz_xyz', database=dbname) == (True, True)


@pytest.mark.parametrize(
    'tag, payload, expected',
    [
        # Only ReadyForQuery is open access; everything decisive else is try-vault.
        (b'R', struct.pack('!I', 3), (True, True)),  # cleartext password
        (b'R', struct.pack('!I', 5) + b'salt', (True, True)),  # MD5
        (b'R', struct.pack('!I', 10), (True, True)),  # SASL
        (b'R', struct.pack('!I', _PG_AUTH_OK), None),  # AuthOk → keep reading
        (b'E', b'SFATAL\x00', (True, True)),
        (b'Z', b'I', (True, False)),  # only open success
        (b'S', b'application_name\x00\x00', None),
        (b'K', b'\x00' * 8, None),
        (b'N', b'', None),
    ],
    ids=[
        'auth-cleartext-try-vault',
        'auth-md5-try-vault',
        'auth-sasl-try-vault',
        'auth-ok-continue',
        'error-try-vault',
        'ready-open',
        'parameter-status',
        'backend-key',
        'notice',
    ],
)
def test_classify_startup_backend_message(tag, payload, expected):
    """Message rules: open only on ReadyForQuery; else try vault or continue."""
    assert PostgresStore._classify_startup_backend_message(tag, payload) == expected


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
        'SELECT data_type FROM information_schema.columns WHERE table_name = ? AND column_name = ?',
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
