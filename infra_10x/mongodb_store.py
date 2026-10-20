from __future__ import annotations

from typing import TYPE_CHECKING, Any

from core_10x.global_cache import cache
from core_10x.nucleus import Nucleus
from core_10x.rc import RC, RC_TRUE
from core_10x.trait_definition import T
from core_10x.ts_store import (
    TS_FIELDS_TAG,
    TsCollection,
    TsDuplicateKeyError,
    TsStore,
    standard_key,
)
from py10x_infra import MongoCollectionHelper
from pymongo import MongoClient, ReturnDocument
from pymongo.common import TIMEOUT_OPTIONS
from pymongo.errors import ConnectionFailure, DuplicateKeyError, OperationFailure, ServerSelectionTimeoutError
from pymongo.uri_parser import parse_uri as pymongo_parse_uri

from infra_10x.namespace import ACTION

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from datetime import datetime

    from core_10x.ts_store import f
    from pymongo.collection import Collection
    from pymongo.database import Database

_REV = Nucleus.REVISION_TAG()
_TS_TIME = T.TS_TIME.value()
_TS_USER = T.TS_USER.value()


class MongoCollection(TsCollection):
    s_id_tag = '_id'

    assert Nucleus.ID_TAG() == s_id_tag, f"Nucleus.ID_TAG() must be '{s_id_tag}'"

    def __init__(self, db, collection_name: str, store: MongoStore):
        self.coll: Collection = db[collection_name]
        self.store = store

    def _session_kw(self):
        tx = self.store.current_transaction()
        return {'session': tx.session} if tx is not None else {}

    def _apply_update(
        self,
        filter: dict,
        update: Mapping[str, Any] | list,
        *,
        upsert: bool,
        rev: int,
        ts_fields: dict,
    ) -> tuple[dict, int]:
        if not ts_fields:
            res = self.coll.update_one(filter, update, upsert=upsert, **self._session_kw())
            assert res.acknowledged, f'{self.coll} update_one not acknowledged'
            return {_REV: rev + int(res.matched_count == 1 and res.modified_count == 1)}, res.matched_count

        doc = self.coll.find_one_and_update(
            filter,
            update,
            upsert=upsert,
            return_document=ReturnDocument.AFTER,
            **self._session_kw(),
        )
        if not doc:
            return {_REV: rev}, 0
        new_rev = doc[_REV]
        assert new_rev in (rev, rev + 1)
        return {_REV: new_rev, **{f: v for f in ts_fields if (v := doc.get(f, doc)) is not doc}}, 1

    def collection_name(self) -> str:
        return self.coll.name

    def id_exists(self, id_value: str) -> bool:
        return self.coll.count_documents({self.s_id_tag: id_value}, **self._session_kw()) > 0

    def find(self, query: f = None, _at_most: int = 0, _order: dict = None) -> Iterable:
        cursor = self.coll.find(query.prefix_notation() if query else {}, **self._session_kw())
        if _order:
            cursor = cursor.sort(list(_order.items()))
        if _at_most:
            cursor = cursor.limit(_at_most)
        return cursor

    def count(self, query: f = None) -> int:
        return self.coll.count_documents(query.prefix_notation() if query else {}, **self._session_kw())

    def _prepare_to_save(self, serialized_traitable):
        doc = dict(serialized_traitable)
        ts_fields = doc.pop(TS_FIELDS_TAG, None) or {}
        doc |= {field: self.store.auth_user() for field, kind in ts_fields.items() if kind == _TS_USER}
        return doc, ts_fields, doc[self.s_id_tag]

    def save_new(self, serialized_traitable: dict, overwrite: bool = False) -> dict:
        doc, ts_fields, id_value = self._prepare_to_save(serialized_traitable)
        rev_tag = _REV

        # TODO: overwrite via save(), not save_new() so that revision is incremented rather than reset
        doc[rev_tag] = 1

        try:
            if not ts_fields and not overwrite:
                res = self.coll.insert_one(doc, **self._session_kw())
                assert res.acknowledged, f'{self.coll} insert_one not acknowledged for {self.s_id_tag}={id_value!r}'
                return {rev_tag: 1}

            result, _matched = self._apply_update(
                {self.s_id_tag: id_value} if overwrite else {self.s_id_tag: id_value, rev_tag: {'$exists': False}},
                [{'$replaceWith': {'$literal': doc}}, *({'$set': {field: '$$NOW'}} for field, kind in ts_fields.items() if kind == _TS_TIME)],
                upsert=True,
                rev=1,
                ts_fields=ts_fields,
            )
        except DuplicateKeyError as e:
            raise TsDuplicateKeyError(self.collection_name(), {self.s_id_tag: id_value}) from e

        result[rev_tag] = 1
        return result

    def save(self, serialized_traitable: dict) -> dict:
        revision = serialized_traitable.get(_REV, -1)
        assert revision >= 0, 'revision must be >= 0'

        if revision == 0:
            return self.save_new(serialized_traitable)

        doc, ts_fields, id_value = self._prepare_to_save(serialized_traitable)

        filter = {}
        pipeline = []
        MongoCollectionHelper.prepare_filter_and_pipeline(doc, filter, pipeline)
        pipeline.extend({'$set': {field: '$$NOW'}} for field, kind in ts_fields.items() if kind == _TS_TIME)
        result, matched = self._apply_update(filter, pipeline, upsert=False, rev=revision, ts_fields=ts_fields)

        if not matched:  # -- e.g. restore from deleted
            raise AssertionError(f'{self.coll} {id_value} has been most probably inappropriately restored from deleted')

        return result

    def delete(self, id_value: str) -> bool:
        q = {self.s_id_tag: id_value}
        return self.coll.delete_one(q, **self._session_kw()).acknowledged

    def create_index(self, name: str, trait_name: str | list[tuple[str, int]], **index_args) -> str | None:
        """Create index. When inside a transaction, defers to run on commit (MongoDB disallows createIndex in txn)."""
        tx = self.store.current_transaction()
        if tx is not None:
            tx.pending_create_index.append((self.collection_name(), name, trait_name, dict(index_args)))
            return name
        sk = self._session_kw()
        index_info = self.coll.index_information(**sk)
        if name in index_info:
            return None

        return self.coll.create_index(trait_name, name=name, **{**index_args, **sk})

    def max(self, trait_name: str, filter: f = None) -> dict | None:
        if filter:
            cur = self.coll.find(filter.prefix_notation(), **self._session_kw()).sort({trait_name: -1}).limit(1)
        else:
            cur = self.coll.find(**self._session_kw()).sort({trait_name: -1}).limit(1)
        for data in cur:
            return data

        return None

    def min(self, trait_name: str, filter: f = None) -> dict | None:
        if filter:
            cur = self.coll.find(filter.prefix_notation(), **self._session_kw()).sort({trait_name: 1}).limit(1)
        else:
            cur = self.coll.find(**self._session_kw()).sort({trait_name: 1}).limit(1)
        for data in cur:
            return data

        return None

    def load(self, id_value: str) -> dict | None:
        for data in self.coll.find({self.s_id_tag: id_value}, **self._session_kw()):
            return data

        return None


class MongoStore(TsStore, resource_name = 'MONGO_DB'):
    ADMIN           = 'admin'
    DEFAULT_DB_NAME = 'local'

    s_instance_kwargs_map = TsStore.s_instance_kwargs_map | dict(
        port    = ('port',                      27017),
        ssl     = ('ssl',                       False),
        sst     = ('serverSelectionTimeoutMS',  10000),
        direct  = ('directConnection', False),
    )

    s_cached_connections: dict[tuple, MongoClient] = {}

    class Transaction(TsStore.Transaction):
        def __init__(self, store: MongoStore):
            if not (current_tx := store.current_transaction()):
                self.session = session = store.client.start_session()
                session.start_transaction()
                self.pending_create_index: list[tuple[str, str, str | list[tuple[str, int]], dict]] = []
            else:
                self.session = current_tx.session
                self.pending_create_index = current_tx.pending_create_index
            super().__init__(store)

        def _do_commit(self) -> None:
            if self.store.current_transaction():
                return  # -- no nested transactions supported
            try:
                self.session.commit_transaction()
            finally:
                self.session.end_session()
            self._run_pending_create_index()

        def _run_pending_create_index(self) -> None:
            """Run create_index calls that were deferred during the transaction (MongoDB disallows createIndex in txn)."""
            for coll_name, name, trait_name, index_args in self.pending_create_index:
                coll = self.store.collection(coll_name, {})  # Mongo ignores trait_dir
                coll.create_index(name, trait_name, **index_args)
            self.pending_create_index.clear()

        def _do_abort(self) -> None:
            if self.store.current_transaction():
                return  # -- no nested transactions supported
            try:
                self.session.abort_transaction()
            finally:
                self.session.end_session()

    @classmethod
    def connect(cls, hostname: str, username: str, password: str, _cache: bool = True, _throw: bool = True, **kwargs) -> MongoClient:
        connection_key = standard_key((hostname, username), kwargs) if _cache else None
        client = cls.s_cached_connections.get(connection_key)
        if not client:
            client = MongoClient(hostname, username=username, password=password, **kwargs)
            try:
                client.server_info()
            except Exception:
                client.close()
                if _throw:
                    raise
                client = None
        if client and connection_key:
            cls.s_cached_connections[connection_key] = client

        return client

    @classmethod
    def uncache_connection(cls, hostname: str, username: str, password: str, **kwargs):
        connection_key = standard_key((hostname, username), kwargs)
        client = cls.s_cached_connections.pop(connection_key, None)
        if client:
            client.close()

    # noinspection PyMethodOverriding
    @classmethod
    def new_instance(cls, hostname: str, dbname: str, username: str, password: str, **kwargs) -> TsStore:
        client = cls.connect(hostname, username, password, **kwargs)
        if not dbname:
            dbname = cls.DEFAULT_DB_NAME
        return cls(client, client[dbname], username)

    @classmethod
    def parse_uri(cls, uri: str) -> dict:
        try:
            aliases = { short: real for short, (real, _) in cls.s_instance_kwargs_map.items() if short != real }
            for short, real in aliases.items():  # aliases are not valid uri params for mongo, so rewrite them
                uri = uri.replace(f'?{short}=', f'?{real}=').replace(f'&{short}=', f'&{real}=')
            params = pymongo_parse_uri(uri)
            # fmt: off
            hostname, port        = params['nodelist'][0]
            kwargs                = params['options']
            kwargs[cls.PORT_TAG]  = port
            args = {
                cls.HOSTNAME_TAG:   hostname,
                cls.DBNAME_TAG:     params['database'],
                cls.USERNAME_TAG:   params['username'],
                cls.PASSWORD_TAG:   params['password'],
            }
            # fmt: on
            args.update(kwargs)
            args.update(  # rename mongo params back to short aliases
                (short, round(value * 1000) if value and real.lower() in TIMEOUT_OPTIONS else value)
                for short, real in aliases.items() if (value := args.pop(real, args)) is not args
            )
            return args
        except Exception as e:
            raise ValueError(f'Invalid URI = {uri}') from e

    def __init__(self, client: MongoClient, db: Database, username: str):
        super().__init__()
        self.client = client
        self.db: Database = db
        self.username = username

    def collection_names(self, regexp: str = None) -> list:
        filter = dict(name={'$regex': regexp}) if regexp else None
        return self.db.list_collection_names(filter=filter)

    def collection(self, collection_name: str, trait_dir: dict | None = None, *, create_if_needed: bool = False) -> MongoCollection:
        return MongoCollection(self.db, collection_name, store=self)  # Mongo is schemaless; trait_dir / create_if_needed unused

    def supports_transactions(self) -> bool:
        """True if this MongoDB deployment supports multi-document transactions (replica set or mongos)."""
        try:
            res = self.client.admin.command('ismaster')
            return 'setName' in res or res.get('msg') == 'isdbgrid'
        except Exception:
            return False

    def delete_collection(self, collection_name: str) -> bool:
        self.db.drop_collection(collection_name)
        return True

    def server_time(self) -> datetime:
        return self.db.command('hello')['localTime']

    @classmethod
    @cache
    def is_running_with_auth(cls, host_name: str, port: int = None) -> tuple:  # -- (is_running, with_auth)
        port = port or cls.s_instance_kwargs_map['port'][1]
        client = MongoClient(host=host_name, port=port, serverSelectionTimeoutMS=10000, directConnection=True)
        try:
            # -- 'hello' works without credentials — confirms the server is reachable
            client.admin.command('hello')
        except (ConnectionFailure, ServerSelectionTimeoutError):
            client.close()
            return (False, False)

        try:
            # -- 'listDatabases' requires auth; if it succeeds unauthenticated, auth is off
            client.admin.command('listDatabases')
            return (True, False)

        except OperationFailure:
            return (True, True)

        finally:
            client.close()

    def list_databases(self, prefix: str = '') -> list[str]:
        return sorted(n for n in self.client.list_database_names() if n.startswith(prefix))

    def delete_database(self, dbname: str) -> bool:
        if dbname not in self.client.list_database_names():
            return False
        self.client.drop_database(dbname)
        return True

    def auth_user(self) -> str:
        return self.username

    def can_serve_as_vault(self) -> bool:
        try:
            host, port = self.client.address
        except Exception:
            return False
        return type(self).is_running_with_auth(host, port)[1]

    def setup_vault_roles(
        self,
        *,
        user_collection: str,
        user_history: str,
        accessor_collection: str,
        accessor_history: str,
        worker_role: str | None = None,
        admin_role: str | None = None,
    ) -> RC:
        worker_role = worker_role or TsStore.VAULT_WORKER_ROLE
        admin_role = admin_role or TsStore.VAULT_ADMIN_ROLE
        admin = self.client[MongoStore.ADMIN]
        dbname = self.db_name()
        identity = (user_collection, user_history)
        accessors = (accessor_collection, accessor_history)
        worker_identity = (ACTION.FIND, ACTION.INSERT, ACTION.INDEX_LIST, ACTION.INDEX_CREATE)
        worker_accessor = (*worker_identity, ACTION.UPDATE)
        admin_actions = (*worker_identity, ACTION.UPDATE)
        try:
            privileges = [{'resource': {'db': dbname, 'collection': cname}, 'actions': list(worker_identity)} for cname in identity]
            privileges.extend({'resource': {'db': dbname, 'collection': cname}, 'actions': list(worker_accessor)} for cname in accessors)
            privileges.append({'resource': {'db': dbname, 'collection': ''}, 'actions': [ACTION.COLL_LIST]})
            method = 'updateRole' if self._vault_role_exists(admin, worker_role) else 'createRole'
            admin.command(method, worker_role, privileges=privileges, roles=[])
            admin_privs = [{'resource': {'db': dbname, 'collection': cname}, 'actions': list(admin_actions)} for cname in (*identity, *accessors)]
            admin_privs.append({'resource': {'db': dbname, 'collection': ''}, 'actions': [ACTION.COLL_LIST]})
            method = 'updateRole' if self._vault_role_exists(admin, admin_role) else 'createRole'
            admin.command(method, admin_role, privileges=admin_privs, roles=[])
        except Exception as e:
            return RC(False, f'Mongo vault role setup failed: {e}')
        return RC_TRUE

    def create_vault_user(self, username: str, password: str, *, worker_role: str | None = None, admin_role: str | None = None) -> RC:
        return self._grant_vault_login(
            username, password, role=worker_role or TsStore.VAULT_WORKER_ROLE, other_role=admin_role or TsStore.VAULT_ADMIN_ROLE
        )

    def create_vault_admin(self, username: str, password: str, *, worker_role: str | None = None, admin_role: str | None = None) -> RC:
        return self._grant_vault_login(
            username, password, role=admin_role or TsStore.VAULT_ADMIN_ROLE, other_role=worker_role or TsStore.VAULT_WORKER_ROLE
        )

    def is_vault_admin(self, *, admin_role: str | None = None) -> bool:
        admin_role = admin_role or TsStore.VAULT_ADMIN_ROLE
        try:
            status = self.client.admin.command('connectionStatus', showPrivileges=False)
        except Exception:
            return False
        roles = (status.get('authInfo') or {}).get('authenticatedUserRoles') or []
        return any(r.get('role') == admin_role and r.get('db') == MongoStore.ADMIN for r in roles)

    @staticmethod
    def _vault_role_exists(admin, role: str) -> bool:
        res = admin.command('rolesInfo', {'role': role, 'db': MongoStore.ADMIN})
        return bool(res.get('roles'))

    def _grant_vault_login(self, username: str, password: str, *, role: str, other_role: str) -> RC:
        if not password:
            return RC(False, 'password is required to create a vault login')
        admin = self.client[MongoStore.ADMIN]
        vault_role = {'role': role, 'db': MongoStore.ADMIN}
        drop = {role, other_role}
        try:
            users = admin.command('usersInfo', {'user': username, 'db': MongoStore.ADMIN}).get('users') or []
            if users:
                kept = [r for r in (users[0].get('roles') or []) if r.get('role') not in drop]
                admin.command('updateUser', username, pwd=password, roles=[*kept, vault_role])
            else:
                admin.command('createUser', username, pwd=password, roles=[vault_role])
        except Exception as e:
            return RC(False, f'Mongo vault login {username!r} failed: {e}')
        return RC_TRUE

    def db_name(self) -> str:
        return self.db.name
