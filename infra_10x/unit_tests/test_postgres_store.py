"""PostgreSQL-specific dialect tests (shared TsStore suites run via conftest ts_instance matrix;
shared IbisStore/index suites run via test_ibis_store.py, parameterized over DuckDB + Postgres)."""

from __future__ import annotations

import getpass
import os
import socket
import ssl
import struct
from contextlib import nullcontext
from datetime import datetime  # used as runtime trait data_type

import ibis
import pytest
import uuid6
from core_10x.testlib import test_databases
from core_10x.testlib.strict import need
from core_10x.trait_definition import T
from core_10x.traitable import Traitable, VaultResourceAccessor
from core_10x.ts_store import TsStore
from core_10x.ts_store_type import TS_STORE_TYPE
from dev_10x.postgres_local import PASSWORD_AUTH_PASSWORD, PASSWORD_AUTH_PORT
from infra_10x.ibis_store import _DATA, _ID, _REV
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
    # Same URI the shared suite fixture uses.
    assert test_databases.test_uri(TEST_TS_STORE.POSTGRESQL.name).startswith('postgresql://localhost/py10x_test')
    assert TEST_TS_STORE.POSTGRESQL.value.helper_flags == (False,)
    assert not TEST_TS_STORE.POSTGRESQL.value.hard_require


def _short_lived_postgres(uri: str) -> PostgresStore:
    """Connect outside the session fixture without caching in ``s_instances``."""
    store = TsStore.instance_from_uri(uri, _cache=False)
    assert isinstance(store, PostgresStore)
    return store


def test_passwordless_connect_userless_uri_uses_os_user(postgres_store):
    """URI without userinfo: Resource.username is None; server role is the OS user."""
    uri = test_databases.test_uri(TEST_TS_STORE.POSTGRESQL.name)
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
    uri = test_databases.test_uri(TEST_TS_STORE.POSTGRESQL.name)
    spec = TsStore.spec_from_uri(uri)
    assert PostgresStore.is_running_with_auth(spec.hostname(), spec.port()) == (True, False)


def test_is_running_with_auth_unknown_role_try_vault(postgres_store):
    """Unknown role: ErrorResponse after handshake → (True, True) so vault is tried."""
    uri = test_databases.test_uri(TEST_TS_STORE.POSTGRESQL.name)
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


def test_fresh_connection_sees_existing_collections(postgres_store):
    """Catalog-backed listing: a store that never opened the collection still finds it.

    Postgres is the first *persistent* ibis dialect, so a handle-backed listing would return
    ``[]`` on a fresh connection and make store-wide ``copy_to`` a silent no-op. The long
    name is the interesting case — its physical table is hashed past NAMEDATALEN, so the
    logical name can only come back from the comment stamped at CREATE time.
    """

    class Pad(Traitable, custom_collection=True, keep_history=False):
        pad: int = T()

    store = postgres_store
    short_name = f'pg_catalog_{os.getpid()}'
    long_name = 'core_10x/testlib/ts_tests/Catalog#' + 'a' * 40
    assert len(long_name.encode()) > 63
    for name in (short_name, long_name):
        store.delete_collection(name)  # -- leftover from an interrupted earlier run
        store.collection(name, Pad.s_dir).save_new({'_id': 'a', 'pad': 1})

    fresh = _short_lived_postgres(test_databases.test_uri(TEST_TS_STORE.POSTGRESQL.name))
    try:
        assert not fresh._collections, 'fixture must not have opened anything on this connection'
        names = fresh.collection_names()
        assert short_name in names
        assert long_name in names, 'hashed physical name must round-trip via the stamped table comment'
        assert fresh.collection(long_name, Pad.s_dir).load('a')['pad'] == 1
    finally:
        store.delete_collection(short_name)
        store.delete_collection(long_name)


def _pg_has_index(store: PostgresStore, collection_name: str, logical_name: str) -> bool:
    phys_table = store._physical_table_name(collection_name)
    phys_idx = store._physical_index_name(collection_name, logical_name)
    rows = store._execute(
        'SELECT 1 FROM pg_indexes WHERE tablename = ? AND indexname = ?',
        [phys_table, phys_idx],
    )
    return bool(rows)


def test_jsonb_path_index_on_blob_field(postgres_store):
    """Blob keys are indexable via (_data ->> 'field') expression indexes — Postgres-only (JSONB)."""

    class Pad(Traitable, custom_collection=True, keep_history=False):
        pad: int = T()

    store = postgres_store
    coll_name = f'pg_jsonb_idx_{os.getpid()}'
    try:
        coll = store.collection(coll_name, Pad.s_dir)
        coll.save_new({'_id': '1', 'pad': 0, 'blob_key': 'v'})
        assert coll.create_index('idx_blob_key', 'blob_key') == 'idx_blob_key'
        assert _pg_has_index(store, coll_name, 'idx_blob_key')
        expr = store._index_expr(coll_name, 'blob_key')
        assert expr is not None and _DATA in expr
    finally:
        store.delete_collection(coll_name)


def test_instance_from_uri(postgres_store):
    uri = test_databases.test_uri(TEST_TS_STORE.POSTGRESQL.name)
    store = TsStore.instance_from_uri(uri, _cache=False)
    assert isinstance(store, PostgresStore)
    assert store.auth_user() is not None


def test_list_databases_prefix_underscores_are_literal(postgres_store):
    """``list_databases`` must not treat ``_`` in the prefix as a LIKE wildcard.

    ``TEST_DB_PREFIX`` is ``py10x_test``; a LIKE ``py10x_test%`` would also match
    ``py10xXtest…``, and ``xx-test-db-clean drop`` would delete those. Mongo uses
    ``str.startswith``; Postgres must match that literal-prefix contract.
    """
    # Maintenance DB — CREATE/DROP DATABASE cannot run against the target itself.
    store = _short_lived_postgres(test_databases.test_uri(TEST_TS_STORE.POSTGRESQL.name, session_db='postgres'))
    prefix = test_databases.TEST_DB_PREFIX
    uid = uuid6.uuid7().hex[:8]
    real = f'{prefix}_lit_{uid}'
    decoy = prefix.replace('_', 'X', 1) + f'_decoy_{uid}'  # matches LIKE, not startswith
    try:
        for name in (real, decoy):
            store._execute(f'CREATE DATABASE {store._qdb(name)}')
        names = store.list_databases(prefix)
        assert real in names
        assert decoy not in names
    finally:
        for name in (real, decoy):
            store.delete_database(name)


def test_rewrite_qmark_binds_skips_literals_and_jsonb_ops():
    assert PostgresStore._rewrite_qmark_binds('SELECT ? WHERE x = ?') == 'SELECT %s WHERE x = %s'
    assert PostgresStore._rewrite_qmark_binds("SELECT '?' , ?") == "SELECT '?' , %s"
    assert PostgresStore._rewrite_qmark_binds('SELECT a ?| b , c ?& d , ?') == 'SELECT a ?| b , c ?& d , %s'


def test_parse_uri_sslmode_and_ibis_connect_kwargs(monkeypatch):
    args = PostgresStore.parse_uri('postgresql://h:5432/db?sslmode=require')
    assert args[PostgresStore.SSL_TAG] is True
    assert args[PostgresStore.SSLMODE_TAG] == 'require'
    captured = {}

    def fake_connect(**kwargs):
        captured.update(kwargs)

        class _Backend:
            con = None

        return _Backend()

    monkeypatch.setattr(ibis.postgres, 'connect', fake_connect)
    PostgresStore(hostname='h', port=5432, dbname='db', username='u', password='p', ssl=True, sslmode='require')
    assert captured.get(PostgresStore.SSLMODE_TAG) == 'require'
    captured.clear()
    PostgresStore(hostname='h', port=5432, dbname='db', username='u', password='p', ssl=True)
    assert captured.get(PostgresStore.SSLMODE_TAG) == 'require'
    captured.clear()
    PostgresStore(hostname='h', port=5432, dbname='db', username='u', password='p')
    assert PostgresStore.SSLMODE_TAG not in captured


def test_startup_probe_ssl_wrap_failure_tries_vault(monkeypatch):
    """Post-TCP SSL negotiation failure → (True, True) so vault is tried."""

    class _Sock:
        def settimeout(self, _t): ...
        def sendall(self, _data): ...
        def recv(self, n):
            return b'S'[:n]

        def close(self): ...

    monkeypatch.setattr(socket, 'create_connection', lambda *a, **k: _Sock())
    monkeypatch.setattr(ssl.SSLContext, 'wrap_socket', lambda self, *a, **k: (_ for _ in ()).throw(ssl.SSLError('bad cert')))
    assert PostgresStore.is_running_with_auth('ssl-fail.example', 55432) == (True, True)


def test_store_from_uri_uses_vault_when_auth_required(monkeypatch):
    sentinel = object()
    captured = {}

    class _FakeSecKeys:
        def decrypt_text(self, _password):
            return 'vault-secret'

    class _FakeUser:
        sec_keys = _FakeSecKeys()

    class _FakeRA:
        login = 'vault-user'
        password = b'encrypted'
        user = _FakeUser()
        resource_uri = 'postgresql://vault-pg.example:5432/postgres'
        _create_resource_if_needed = False

        @property
        def resource(self):
            # Mirror VaultResourceAccessor.resource_get: honor the stamp from retrieve_ra.
            return PostgresStore.instance_from_uri(
                self.resource_uri,
                username=self.login,
                password=self.user.sec_keys.decrypt_text(self.password),
                _create_if_needed=self._create_resource_if_needed,
            )

    def _fake_retrieve_ra(cls, resource_dt, resource_uri, username=None, *, _create_resource_if_needed=False):
        ra = _FakeRA()
        ra.resource_uri = resource_uri
        ra._create_resource_if_needed = _create_resource_if_needed
        return ra

    def _fake_instance_from_uri(cls, uri, username=None, password=None, _cache=True, _create_if_needed=False):
        captured.update(uri=uri, username=username, password=password, _create_if_needed=_create_if_needed)
        return sentinel

    monkeypatch.setattr(PostgresStore, 'is_running_with_auth', classmethod(lambda cls, host_name, port=None: (True, True)))
    monkeypatch.setattr(Traitable, 'vault_store', staticmethod(lambda: nullcontext()))
    monkeypatch.setattr(VaultResourceAccessor, 'retrieve_ra', classmethod(_fake_retrieve_ra))
    monkeypatch.setattr(PostgresStore, 'instance_from_uri', classmethod(_fake_instance_from_uri))

    uri = 'postgresql://vault-pg.example:5432/postgres'
    assert Traitable.store_from_uri(uri) is sentinel
    assert captured == {'uri': uri, 'username': 'vault-user', 'password': 'vault-secret', '_create_if_needed': False}

    assert Traitable.store_from_uri(uri, _create_if_needed=True) is sentinel
    assert captured['_create_if_needed'] is True


def test_resource_instance_create_if_needed_runs_before_new_instance(monkeypatch):
    """``Resource.instance(..., _create_if_needed=True)`` creates only when constructing a new instance."""
    order = []

    monkeypatch.setattr(PostgresStore, 'create_if_needed', classmethod(lambda cls, spec: order.append(('create', spec.kwargs['dbname'])) or False))
    monkeypatch.setattr(PostgresStore, 'new_instance', classmethod(lambda cls, **kw: order.append(('new', kw.get('dbname'))) or object()))

    kw = {'hostname': 'localhost', 'port': 5432, 'dbname': 'to_create', 'username': 'u', 'password': 'p', '_create_if_needed': True}
    PostgresStore.instance(**kw, _cache=False)
    assert order == [('create', 'to_create'), ('new', 'to_create')]

    order.clear()
    PostgresStore.s_instances.clear()
    PostgresStore.instance(**kw)  # cache miss -> create + new
    assert order == [('create', 'to_create'), ('new', 'to_create')]

    order.clear()
    PostgresStore.instance(**kw)  # cache hit -> neither
    assert order == []


def test_password_auth_probe_requires_auth():
    running, with_auth = PostgresStore.is_running_with_auth('localhost', PASSWORD_AUTH_PORT)
    need(running, f'password-auth Postgres not running on localhost:{PASSWORD_AUTH_PORT}')
    assert with_auth is True


def test_password_auth_connect():
    need(
        PostgresStore.is_running_with_auth('localhost', PASSWORD_AUTH_PORT)[0],
        f'password-auth Postgres not running on localhost:{PASSWORD_AUTH_PORT}',
    )
    store = PostgresStore.instance(
        hostname='localhost',
        port=PASSWORD_AUTH_PORT,
        dbname='postgres',
        username='postgres',
        password=PASSWORD_AUTH_PASSWORD,
        _cache=False,
    )
    assert store._execute('SELECT 1')[0][0] == 1
    assert store.auth_user() == 'postgres'
