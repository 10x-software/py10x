from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from core_10x.global_cache import cache
from core_10x.nucleus import Nucleus
from core_10x.ts_store import (
    TsCollection,
    TsDuplicateKeyError,
    TsStore,
    standard_key,
)
from py10x_infra import MongoCollectionHelper
from pymongo import MongoClient, ReturnDocument, errors
from pymongo.errors import DuplicateKeyError, ConnectionFailure, OperationFailure, ServerSelectionTimeoutError
from pymongo.uri_parser import parse_uri as pymongo_parse_uri

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from core_10x.ts_store import f
    from pymongo.collection import Collection
    from pymongo.database import Database

_REV = Nucleus.REVISION_TAG()

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
        upsert: bool = False,
        rev: int,
        ts_trait_names: Sequence[str] = (),
    ) -> tuple[dict, int]:
        if not ts_trait_names:
            res = self.coll.update_one(filter, update, upsert=upsert, **self._session_kw())
            assert res.acknowledged, f'{self.coll} update_one not acknowledged'
            return {_REV: rev + int(
                res.matched_count == 1 and res.modified_count == 1)}, res.matched_count

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
        return {_REV: new_rev, **{field: doc[field] for field in ts_trait_names}}, 1


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

    def save_new(self, serialized_traitable: dict, overwrite: bool = False, ts_trait_names: Sequence[str] = ()) -> dict:
        needs_upsert = bool(ts_trait_names) or overwrite
        set_values = serialized_traitable.get('$set')
        id_tag = self.s_id_tag
        id_value = (set_values or serialized_traitable)[id_tag]
        rev_tag = _REV

        # TODO: overwrite via save(), not save_new() so that revision is incremented rather than reset
        (set_values or serialized_traitable)[rev_tag] = 1

        sk = self._session_kw()
        try:
            if not needs_upsert:
                res = self.coll.insert_one(serialized_traitable, **sk)
                assert res.acknowledged, f'{self.coll} insert_one not acknowledged for {id_tag}={id_value!r}'
                return {rev_tag: 1}

            result, _matched = self._apply_update(
                {id_tag: id_value} if overwrite else {id_tag: id_value, rev_tag: {'$exists': False}},
                serialized_traitable if set_values else {'$set': serialized_traitable},
                upsert=True,
                rev=1,
                ts_trait_names=ts_trait_names,
            )
        except DuplicateKeyError as e:
            raise TsDuplicateKeyError(self.collection_name(), {id_tag: id_value}) from e

        return result

    def save(self, serialized_traitable: dict, ts_trait_names: Sequence[str] = ()) -> dict:
        rev_tag = _REV
        id_tag = self.s_id_tag

        revision = serialized_traitable.get(rev_tag, -1)
        assert revision >= 0, 'revision must be >= 0'

        if revision == 0:
            return self.save_new(serialized_traitable, ts_trait_names=ts_trait_names)

        id_value = serialized_traitable.get(id_tag)

        filter = {}
        pipeline = []
        serialized_traitable = dict(serialized_traitable)  # -- copy to avoid modifying the input
        MongoCollectionHelper.prepare_filter_and_pipeline(serialized_traitable, filter, pipeline)

        result, matched = self._apply_update(
            filter, pipeline, rev=revision, ts_trait_names=ts_trait_names
        )

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
                coll = self.store.collection(coll_name)
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
            params = pymongo_parse_uri(uri)
            # fmt: off
            hostname, port  = params['nodelist'][0]
            kwargs          = params['options']
            kwargs[cls.PORT_TAG]  = port
            args = {
                cls.HOSTNAME_TAG:   hostname,
                cls.DBNAME_TAG:     params['database'],
                cls.USERNAME_TAG:   params['username'],
                cls.PASSWORD_TAG:   params['password'],
            }
            # fmt: on
            args.update(kwargs)
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

    def collection(self, collection_name: str) -> TsCollection:
        return MongoCollection(self.db, collection_name, store=self)

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
    def is_running_with_auth(cls, host_name: str, port: int) -> tuple:  # -- (is_running, with_auth)
        client = MongoClient(host = host_name, port = port, serverSelectionTimeoutMS = 10000, directConnection = True)
        try:
            #-- 'hello' works without credentials — confirms the server is reachable
            client.admin.command('hello')
        except (ConnectionFailure, ServerSelectionTimeoutError):
            client.close()
            return (False, False)

        try:
            #-- 'listDatabases' requires auth; if it succeeds unauthenticated, auth is off
            client.admin.command('listDatabases')
            return (True, False)

        except OperationFailure:
            return (True, True)

        finally:
            client.close()

    def auth_user(self) -> str:
        return self.username

    def db_name(self) -> str:
        return self.db.name

    def add_who(self, field: str, serialized_data: dict) -> dict:
        sd = serialized_data.get('$set', serialized_data)
        if field in sd:
            raise RuntimeError(f'Field {field} is already in use.')
        sd[field] = self.auth_user()
        return serialized_data

    def add_when(self, field: str, serialized_data: dict) -> dict:
        sd = serialized_data.get('$set', serialized_data)
        if field in sd:
            raise RuntimeError(f'Field {field} is already in use.')
        if sd is serialized_data:
            sd = dict(sd)
            serialized_data.clear()
            serialized_data['$set'] = sd
        serialized_data.setdefault('$currentDate', {})[field] = True
        return serialized_data
