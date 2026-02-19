from __future__ import annotations

import abc
from contextlib import contextmanager
from typing import TYPE_CHECKING

from core_10x.exec_control import ProcessContext
from core_10x.global_cache import standard_key
from core_10x.py_class import PyClass
from core_10x.rc import RC
from core_10x.resource import TS_STORE, Resource, ResourceSpec
from core_10x.trait_filter import f
from core_10x.ts_store_type import TS_STORE_TYPE

if TYPE_CHECKING:
    from collections.abc import Iterable


class TsDuplicateKeyError(Exception):
    """Raised when attempting to insert a document with a duplicate key."""

    def __init__(self, collection_name: str, duplicate_key: dict):
        super().__init__(f'Duplicate key error collection {collection_name} dup key: {duplicate_key} was found while insert was attempted.')


class TsCollection(abc.ABC):
    s_id_tag: str = None

    @abc.abstractmethod
    def collection_name(self) -> str: ...
    @abc.abstractmethod
    def id_exists(self, id_value: str) -> bool: ...
    @abc.abstractmethod
    def find(self, query: f = None, _at_most: int = 0, _order: dict = None) -> Iterable: ...
    @abc.abstractmethod
    def count(self, query: f = None) -> int: ...
    @abc.abstractmethod
    def save_new(self, serialized_traitable: dict, overwrite: bool = False) -> int: ...
    @abc.abstractmethod
    def save(self, serialized_traitable: dict) -> int: ...
    @abc.abstractmethod
    def delete(self, id_value: str) -> bool: ...
    @abc.abstractmethod
    def create_index(self, name: str, trait_name: str | list[tuple[str, int]], **index_args) -> str: ...
    @abc.abstractmethod
    def max(self, trait_name: str, filter: f = None) -> dict: ...
    @abc.abstractmethod
    def min(self, trait_name: str, filter: f = None) -> dict: ...

    def exists(self, query: f) -> bool:
        return self.count(query) > 0

    def load(self, id_value: str) -> dict | None:
        for data in self.find(f(**{self.s_id_tag: id_value})):
            return data

    def copy_to(self, to_coll: TsCollection, overwrite: bool = False) -> RC:
        """Copy all documents from this collection to another collection."""
        rc = RC(True)

        for doc in self.find():
            try:
                if not to_coll.save_new(doc, overwrite=overwrite):
                    rc.add_error(f'Failed to save {doc.get(to_coll.s_id_tag)} to {to_coll.collection_name()}')
            except TsDuplicateKeyError:
                if overwrite:
                    raise  # -- we do not expect an exception in case of overwrite, so raise

        return rc


class TsTransaction(abc.ABC):
    """Transaction handle with manual commit() and abort(). Subclasses must implement _do_commit and _do_abort."""

    _ended: bool = False

    def commit(self) -> None:
        """Commit the transaction. No-op if already ended."""
        if self._ended:
            return
        self._ended = True
        self._do_commit()
        self._unregister_from_store()

    def abort(self) -> None:
        """Abort the transaction. No-op if already ended."""
        if self._ended:
            return
        self._ended = True
        self._do_abort()
        self._unregister_from_store()

    def _unregister_from_store(self) -> None:
        """Override to clear store._current_tx when this transaction is the current one. No-op by default."""
        pass

    @abc.abstractmethod
    def _do_commit(self) -> None: ...

    @abc.abstractmethod
    def _do_abort(self) -> None: ...


class TsStore(Resource, resource_type=TS_STORE):
    PROTOCOL = ''

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        assert cls.__mro__[1] is TsStore, 'TsStore must be the first base class'
        cls.s_instance_kwargs_map = {**TsStore.s_instance_kwargs_map, **cls.s_instance_kwargs_map}

    @staticmethod
    def store_class(store_class_name: str):
        cls = PyClass.find(store_class_name, TsStore)
        assert cls, f'Unknown TsStore class {store_class_name}'
        return cls

    @classmethod
    def standard_key(cls, *args, **kwargs) -> tuple:
        return standard_key(args, kwargs)

    s_instances = {}

    @classmethod
    def spec_from_uri(cls, uri: str) -> ResourceSpec:
        parts = uri.split(':', maxsplit=1)
        protocol = parts[0]
        ts_class = TS_STORE_TYPE.ts_store_class(protocol)
        return ResourceSpec(ts_class, ts_class.parse_uri(uri))

    @classmethod
    def instance(cls, *args, password: str = '', _cache: bool = True, **kwargs) -> TsStore:
        translated_kwargs = cls.translate_kwargs(kwargs)
        try:
            if not _cache:
                return cls.new_instance(*args, password=password, **translated_kwargs)

            instance_key = cls.standard_key(*args, **kwargs)
            store = cls.s_instances.get(instance_key)
            if not store:
                store = cls.new_instance(*args, password=password, **translated_kwargs)
                cls.s_instances[instance_key] = store

            return store

        except Exception as e:
            raise OSError(f'Failed to connect to {cls.s_driver_name}({args}, {translated_kwargs})\nOriginal Exception:\n{e!s}') from e

    # fmt: off
    s_instance_kwargs_map = {
        Resource.HOSTNAME_TAG:  (Resource.HOSTNAME_TAG, None),
        Resource.USERNAME_TAG:  (Resource.USERNAME_TAG, None),
        Resource.DBNAME_TAG:    (Resource.DBNAME_TAG,   None),
        Resource.PORT_TAG:      (Resource.PORT_TAG,     None),
        Resource.SSL_TAG:       (Resource.SSL_TAG,      True),
        'sst':                  ('sst',                 1000),
    }
    # fmt: on

    @classmethod
    def translate_kwargs(cls, kwargs: dict) -> dict:
        kwargs_map = cls.s_instance_kwargs_map
        def_kwargs = {name: def_value for name, (real_name, def_value) in kwargs_map.items()}
        def_kwargs.update(kwargs)
        return {kwargs_map[name][0]: value for name, value in def_kwargs.items()}

    @classmethod
    def new_instance(cls, *args, password: str, **kwargs) -> TsStore:
        raise NotImplementedError

    @classmethod
    def parse_uri(cls, uri: str) -> dict:
        raise NotImplementedError

    @classmethod
    def is_running_with_auth(cls, host_name: str) -> tuple:   # -- (is_running, with_auth)
        raise NotImplementedError

    def on_enter(self):
        self.bpc_flags = ProcessContext.reset_flags(ProcessContext.CACHE_ONLY)

    def on_exit(self):
        ProcessContext.replace_flags(self.bpc_flags)

    @abc.abstractmethod
    def collection_names(self, regexp: str = None) -> list: ...

    @abc.abstractmethod
    def collection(self, collection_name: str) -> TsCollection: ...

    @abc.abstractmethod
    def delete_collection(self, collection_name: str) -> bool: ...

    @abc.abstractmethod
    def auth_user(self) -> str | None: ...

    def supports_transactions(self) -> bool:
        return True

    def populate(self, params: list[str], serialized_data: dict):
        """Populate specified params on the server, if possible.
        This should be overridden in subclasses as needed"""
        populated_data = {
            '$set': serialized_data,
        }
        for param in sorted(params, reverse=True):
            if param == '_who':
                serialized_data['_who'] = self.auth_user()
                continue
            if param == '_at':
                del serialized_data['_at']
                populated_data['$currentDate'] = {'_at': True}
                continue
            raise KeyError(param)
        return populated_data

    def copy_to(self, to_store: TsStore, overwrite: bool = False) -> RC:
        """Copy all collections from this store to another store."""
        rc = RC(True)

        for collection_name in self.collection_names():
            from_coll = self.collection(collection_name)
            to_coll = to_store.collection(collection_name)
            rc += from_coll.copy_to(to_coll, overwrite=overwrite)

        return rc

    @abc.abstractmethod
    def _begin_transaction(self) -> TsTransaction:
        """Start a transaction and return a transaction object. Must be implemented in subclasses."""
        ...

    @contextmanager
    def transaction(self):
        """Context manager for transactional operations. Yields a transaction object with commit() and abort()."""
        tx = self._begin_transaction()
        success = False
        try:
            yield tx
            success = True
        finally:
            if not tx._ended:
                if success:
                    tx.commit()
                else:
                    tx.abort()
