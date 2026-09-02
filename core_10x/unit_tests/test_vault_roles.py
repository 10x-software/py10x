"""Vault worker/admin DB roles (``xx-vault-setup-roles``)."""

from __future__ import annotations

from types import SimpleNamespace

import core_10x.sec_keys as sec_keys_mod
import core_10x.traitable as traitable_mod
import pytest
import uuid6
from core_10x.environment_variables import EnvVars
from core_10x.global_cache import _clear_all_caches
from core_10x.package_refactoring import PackageRefactoring
from core_10x.resource import Resource
from core_10x.testlib import test_databases
from core_10x.testlib.strict import need
from core_10x.traitable import TraitableHistory, VaultResourceAccessor, VaultUser
from core_10x.ts_store import TsStore
from core_10x.ts_store_type import TS_STORE_TYPE
from core_10x.vault_roles import VaultRoles
from core_10x.vault_utils import VaultUtils
from dev_10x.postgres_local import PASSWORD_AUTH_PASSWORD, PASSWORD_AUTH_PORT, PASSWORD_AUTH_USER
from infra_10x.duckdb_store import DuckDbStore
from infra_10x.mongodb_store import MongoStore
from infra_10x.namespace import ACTION
from infra_10x.postgres_store import PostgresStore
from psycopg.errors import InsufficientPrivilege
from pymongo import MongoClient
from pymongo.errors import OperationFailure


def test_vault_roles_reject_unauthenticated_store(live_store):
    rc = VaultRoles.setup(DuckDbStore.instance(_cache=False))
    assert not rc
    assert 'cannot serve as a vault' in rc.error()

    pg = live_store(TS_STORE_TYPE.POSTGRESQL.name)
    if pg is not None and not pg.can_serve_as_vault():
        rc = VaultRoles.setup(pg)
        assert not rc
        assert 'cannot serve as a vault' in rc.error()


def test_vault_collection_names_include_history():
    names = VaultRoles.vault_collection_names()
    vu = PackageRefactoring.find_class_id(VaultUser)
    assert vu in names
    assert f'{vu}#history' in names
    assert len(names) == 4


def _install_vault_roles(store, *, worker: str, admin_login: str, pwd: str, worker_role: str | None = None, admin_role: str | None = None):
    """GRANTs/RLS even when the server is open (can_serve_as_vault is False)."""
    VaultRoles.ensure_schema(store).throw()
    vu = PackageRefactoring.find_class_id(VaultUser)
    vra = PackageRefactoring.find_class_id(VaultResourceAccessor)
    rc = store.setup_vault_roles(
        user_collection=vu,
        user_history=TraitableHistory.history_collection_name(vu),
        accessor_collection=vra,
        accessor_history=TraitableHistory.history_collection_name(vra),
        worker_role=worker_role,
        admin_role=admin_role,
    )
    assert rc, rc.error()
    rc = store.create_vault_user(worker, pwd, worker_role=worker_role, admin_role=admin_role)
    assert rc, rc.error()
    rc = store.create_vault_admin(admin_login, pwd, worker_role=worker_role, admin_role=admin_role)
    assert rc, rc.error()


def test_postgres_worker_cannot_update_or_insert_foreign_vaultuser(live_store):
    store = live_store(TS_STORE_TYPE.POSTGRESQL.name)
    need(store is not None, f'PostgreSQL not running (at {test_databases.test_uri(TS_STORE_TYPE.POSTGRESQL.name)})')
    assert isinstance(store, PostgresStore)

    suffix = uuid6.uuid7().hex[:8]
    worker, admin_login, other = f'vw_{suffix}', f'va_{suffix}', f'vo_{suffix}'
    pwd = 'VaultTest9!'
    _install_vault_roles(store, worker=worker, admin_login=admin_login, pwd=pwd)
    assert not store.create_vault_user(f'np_{suffix}', '')

    vu = PackageRefactoring.find_class_id(VaultUser)
    vra = PackageRefactoring.find_class_id(VaultResourceAccessor)
    vh = TraitableHistory.history_collection_name(vu)
    quser, qhist, qvra = store._qname(vu), store._qname(vh), store._qname(vra)

    store._execute(f'SET ROLE {PostgresStore._qident(worker)}')
    try:
        assert not store.is_vault_admin()
        store._execute(f'INSERT INTO {quser} (_id, _rev, _data) VALUES (?, 1, ?::jsonb)', [worker, '{}'])
        with pytest.raises(InsufficientPrivilege):
            store._execute(f'INSERT INTO {quser} (_id, _rev, _data) VALUES (?, 1, ?::jsonb)', [other, '{}'])
        with pytest.raises(InsufficientPrivilege):
            store._execute(f'UPDATE {quser} SET _rev = 2 WHERE _id = ?', [worker])
        assert store._execute(f'SELECT _id FROM {quser} WHERE _id = ?', [other]) == []
        store._execute(f'INSERT INTO {qhist} (_id, _rev, _data, "_traitable_id") VALUES (?, 1, ?::jsonb, ?)', [f'h-{worker}', '{}', worker])
        with pytest.raises(InsufficientPrivilege):
            store._execute(f'INSERT INTO {qhist} (_id, _rev, _data, "_traitable_id") VALUES (?, 1, ?::jsonb, ?)', [f'h-{other}', '{}', other])
        store._execute(f'INSERT INTO {qvra} (_id, _rev, _data, username) VALUES (?, 1, ?::jsonb, ?)', [f'{worker}|t|u', '{}', worker])
        store._execute(f'UPDATE {qvra} SET _rev = 2 WHERE _id = ?', [f'{worker}|t|u'])
        with pytest.raises(InsufficientPrivilege):
            store._execute(f'INSERT INTO {qvra} (_id, _rev, _data, username) VALUES (?, 1, ?::jsonb, ?)', [f'{other}|t|u', '{}', other])
    finally:
        store._execute('RESET ROLE')

    store._execute(f'INSERT INTO {qvra} (_id, _rev, _data, username) VALUES (?, 1, ?::jsonb, ?)', [f'{other}|t|u', '{}', other])
    store._execute(f'SET ROLE {PostgresStore._qident(worker)}')
    try:
        store._execute(f'UPDATE {qvra} SET _rev = 2 WHERE _id = ?', [f'{other}|t|u'])
    finally:
        store._execute('RESET ROLE')
    assert store._execute(f'SELECT _rev FROM {qvra} WHERE _id = ?', [f'{other}|t|u']) == [(1,)]

    store._execute(f'SET ROLE {PostgresStore._qident(admin_login)}')
    try:
        assert store.is_vault_admin()
        store._execute(f'UPDATE {quser} SET _rev = 2 WHERE _id = ?', [worker])
        rows = store._execute(f'SELECT _rev FROM {quser} WHERE _id = ?', [worker])
        assert rows and rows[0][0] == 2
    finally:
        store._execute('RESET ROLE')

    for role in (worker, admin_login):
        store._execute(f'DROP OWNED BY {PostgresStore._qident(role)}')
        store._execute(f'DROP ROLE IF EXISTS {PostgresStore._qident(role)}')


def test_mongo_vault_roles_are_not_anyresource(live_store):
    store = live_store(TS_STORE_TYPE.MONGODB.name)
    need(store is not None, f'MongoDB not running (at {test_databases.test_uri(TS_STORE_TYPE.MONGODB.name)})')
    assert isinstance(store, MongoStore)

    suffix = uuid6.uuid7().hex[:8]
    worker_role, admin_role = f'xxVW_{suffix}', f'xxVA_{suffix}'
    VaultRoles.ensure_schema(store).throw()
    vu = PackageRefactoring.find_class_id(VaultUser)
    vra = PackageRefactoring.find_class_id(VaultResourceAccessor)
    rc = store.setup_vault_roles(
        user_collection=vu,
        user_history=TraitableHistory.history_collection_name(vu),
        accessor_collection=vra,
        accessor_history=TraitableHistory.history_collection_name(vra),
        worker_role=worker_role,
        admin_role=admin_role,
    )
    assert rc, rc.error()

    admin = store.client[MongoStore.ADMIN]
    try:
        worker_privs = _mongo_actions(admin, worker_role, store.db_name())
        admin_privs = _mongo_actions(admin, admin_role, store.db_name())
        vu = PackageRefactoring.find_class_id(VaultUser)
        vra = PackageRefactoring.find_class_id(VaultResourceAccessor)
        assert ACTION.FIND in worker_privs[vu]
        assert ACTION.INSERT in worker_privs[vu]
        assert ACTION.UPDATE not in worker_privs[vu]
        assert ACTION.REMOVE not in worker_privs[vu]
        assert ACTION.UPDATE in worker_privs[vra]
        assert ACTION.UPDATE not in worker_privs[vu]
        assert ACTION.UPDATE in admin_privs[vu]
        assert ACTION.REMOVE not in admin_privs[vu]
        assert not any(p.get('resource', {}).get('anyResource') for p in _mongo_role_privileges(admin, worker_role))
    finally:
        for role in (worker_role, admin_role):
            if admin.command('rolesInfo', {'role': role, 'db': MongoStore.ADMIN}).get('roles'):
                admin.command('dropRole', role)


@pytest.mark.xfail(reason='Mongo worker INSERT on VaultUser is collection-wide until document-level rules exist', strict=True)
def test_mongo_worker_cannot_insert_foreign_vaultuser(live_store):
    store = live_store(TS_STORE_TYPE.MONGODB.name)
    need(store is not None, f'MongoDB not running (at {test_databases.test_uri(TS_STORE_TYPE.MONGODB.name)})')
    assert isinstance(store, MongoStore)
    need(store.can_serve_as_vault(), 'authenticated MongoDB required for vault worker enforcement test')

    suffix = uuid6.uuid7().hex[:8]
    worker, other = f'mw_{suffix}', f'mo_{suffix}'
    pwd = 'VaultTest9!'
    worker_role, admin_role = f'xxVW_{suffix}', f'xxVA_{suffix}'
    VaultRoles.ensure_schema(store).throw()
    vu = PackageRefactoring.find_class_id(VaultUser)
    vra = PackageRefactoring.find_class_id(VaultResourceAccessor)
    rc = store.setup_vault_roles(
        user_collection=vu,
        user_history=TraitableHistory.history_collection_name(vu),
        accessor_collection=vra,
        accessor_history=TraitableHistory.history_collection_name(vra),
        worker_role=worker_role,
        admin_role=admin_role,
    )
    assert rc, rc.error()
    rc = store.create_vault_user(worker, pwd, worker_role=worker_role, admin_role=admin_role)
    assert rc, rc.error()

    host, port = store.client.address
    worker_client = MongoClient(
        host=host,
        port=port,
        username=worker,
        password=pwd,
        authSource=MongoStore.ADMIN,
        directConnection=True,
        serverSelectionTimeoutMS=10000,
    )
    admin = store.client[MongoStore.ADMIN]
    try:
        coll = worker_client[store.db_name()][vu]
        coll.insert_one({'_id': worker, '_rev': 1, '_data': {}})
        with pytest.raises(OperationFailure):
            coll.insert_one({'_id': other, '_rev': 1, '_data': {}})
    finally:
        worker_client.close()
        admin.command('dropUser', worker)
        for role in (worker_role, admin_role):
            if admin.command('rolesInfo', {'role': role, 'db': MongoStore.ADMIN}).get('roles'):
                admin.command('dropRole', role)


def _mongo_role_privileges(admin, role: str) -> list:
    info = admin.command('rolesInfo', {'role': role, 'db': MongoStore.ADMIN}, showPrivileges=True)
    roles = info.get('roles') or []
    return roles[0].get('privileges') or [] if roles else []


def _mongo_actions(admin, role: str, dbname: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for priv in _mongo_role_privileges(admin, role):
        resource = priv.get('resource') or {}
        if resource.get('db') != dbname:
            continue
        out[resource.get('collection') or ''] = set(priv.get('actions') or [])
    return out


def test_worker_cannot_admin_save_on_auth_postgres(monkeypatch):
    need(
        PostgresStore.is_running_with_auth('localhost', PASSWORD_AUTH_PORT)[1],
        f'password-auth Postgres not running on localhost:{PASSWORD_AUTH_PORT}',
    )
    dbname = f'py10x_ag_{uuid6.uuid7().hex[:8]}'
    uri = f'postgresql://localhost:{PASSWORD_AUTH_PORT}/{dbname}'
    worker, pwd = f'vw_{uuid6.uuid7().hex[:8]}', 'VaultTest9!'
    admin = PostgresStore.instance_from_uri(
        uri, username=PASSWORD_AUTH_USER, password=PASSWORD_AUTH_PASSWORD, _cache=False, _create_if_needed=True
    )
    assert admin.can_serve_as_vault()
    keyring: dict = {}
    monkeypatch.setattr(sec_keys_mod.keyring, 'get_password', lambda s, u: keyring.get((s, u)))
    monkeypatch.setattr(sec_keys_mod.keyring, 'set_password', lambda s, u, p: keyring.__setitem__((s, u), p))
    fake_os = SimpleNamespace(me=SimpleNamespace(name=lambda: worker))
    monkeypatch.setattr(sec_keys_mod, 'OsUser', fake_os)
    monkeypatch.setattr(traitable_mod, 'OsUser', fake_os)
    monkeypatch.setattr(VaultUser, 'myname', classmethod(lambda cls: worker))
    monkeypatch.setattr(EnvVars, 'main_vault_uri', uri)
    try:
        VaultRoles.setup(admin, worker=worker, worker_password=pwd).throw()
        _clear_all_caches()
        VaultUtils.user_init(login=worker, password=pwd, master_password='MasterPwd9!').throw()
        _clear_all_caches()
        rc = VaultUtils.admin_save_user_credentials()
        assert not rc
        assert 'vault admin role required' in rc.error()
    finally:
        _clear_all_caches()
        TsStore.s_instances.clear()
        maint = PostgresStore.instance_from_uri(
            Resource.uri_no_dbname(uri), username=PASSWORD_AUTH_USER, password=PASSWORD_AUTH_PASSWORD, _cache=False
        )
        maint.delete_database(dbname)
        maint._execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = ?', [worker])
        maint._execute(f'DROP ROLE IF EXISTS {PostgresStore._qident(worker)}')

