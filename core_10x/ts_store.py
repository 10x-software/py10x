from __future__ import annotations

import abc
from collections import deque
from contextlib import ExitStack, contextmanager
from datetime import datetime
from typing import TYPE_CHECKING

#from polars.testing.parametric.strategies import data

from core_10x.environment_variables import EnvVars
from core_10x.exec_control import ProcessContext
from core_10x.global_cache import standard_key
from core_10x.nucleus import Nucleus
from core_10x.py_class import PyClass
from core_10x.rc import RC
from core_10x.resource import TS_STORE, Resource, ResourceSpec
from core_10x.trait_filter import f
from core_10x.ts_store_type import TS_STORE_TYPE
from py10x_kernel import BTraitableProcessorSetValueTracker as BTPTracker

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from core_10x.traitable import Traitable


_REV = Nucleus.REVISION_TAG()


SERVER_TRAITS_TAG = '__ts_server_traits__'


def note_server_trait(serialized_data: dict, field: str) -> None:
    serialized_data.setdefault(SERVER_TRAITS_TAG, []).append(field)


def pop_server_trait_fields(serialized_data: dict) -> list[str]:
    return list(serialized_data.pop(SERVER_TRAITS_TAG, None) or ())


def build_save_result(
    rev: int,
    write_doc: dict,
    returned_doc: dict | None,
    server_trait_fields: list[str],
) -> dict:
    """Build save return value: revision plus server-populated trait values."""
    result = {_REV: rev}
    if not server_trait_fields:
        return result

    current_date_fields = set((write_doc.get('$currentDate') or {}).keys())
    set_doc = write_doc.get('$set', write_doc)
    for field in server_trait_fields:
        if field in current_date_fields:
            if returned_doc is not None and field in returned_doc:
                result[field] = returned_doc[field]
        elif field in set_doc:
            result[field] = set_doc[field]
        elif field in write_doc and field not in ('$set', '$currentDate', SERVER_TRAITS_TAG):
            result[field] = write_doc[field]
        elif returned_doc is not None and field in returned_doc:
            result[field] = returned_doc[field]
    return result


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
    def save_new(self, serialized_traitable: dict, overwrite: bool = False) -> dict: ...
    @abc.abstractmethod
    def save(self, serialized_traitable: dict) -> dict: ...
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
                if not to_coll.save_new(doc, overwrite=overwrite).get(_REV):
                    rc.add_error(f'Failed to save {doc.get(to_coll.s_id_tag)} to {to_coll.collection_name()}')
            except TsDuplicateKeyError:
                if overwrite:
                    raise  # -- we do not expect an exception in case of overwrite, so raise

        return rc



class TsStore(Resource, resource_type=TS_STORE):
    s_instance_kwargs_map = Resource.s_instance_kwargs_map | {
        Resource.SSL_TAG: (Resource.SSL_TAG,    True),
        'sst':            ('sst',               1000),
    }

    class Transaction:
        ended: bool = False

        def __init__(self, store: TsStore):
            self.store = store
            store.begin_transaction(self)

        def commit(self) -> None:
            """Commit the transaction. No-op if already ended."""
            if self.ended:
                return
            self.store.end_transaction(self)
            self._do_commit()

        def abort(self) -> None:
            """Abort the transaction. No-op if already ended."""
            if self.ended:
                return
            self.store.end_transaction(self)
            self._do_abort()


        def _do_commit(self) -> None: ...

        def _do_abort(self) -> None: ...

    def __init__(self):
        self._active_transactions = deque()

    def current_transaction(self) -> Transaction|None:
        return self._active_transactions[-1] if self._active_transactions else None

    def begin_transaction(self, transaction: Transaction) -> None:
        self._active_transactions.append(transaction)

    def end_transaction(self, transaction: Transaction) -> None:
        if transaction != self.current_transaction():
            raise RuntimeError(f'Transaction {transaction} is not currently active.')
        if transaction:
            self._active_transactions.pop()
            transaction.ended = True

    @staticmethod
    def store_class(store_class_name: str):
        cls = PyClass.find(store_class_name, TsStore)
        assert cls, f'Unknown TsStore class {store_class_name}'
        return cls

    @classmethod
    def spec_from_uri(cls, uri: str) -> ResourceSpec:
        parts = uri.split(':', maxsplit=1)
        protocol = parts[0]
        ts_class = TS_STORE_TYPE.ts_store_class(protocol)
        kwargs = ts_class.parse_uri(uri)
        kwargs.setdefault(ts_class.PROTOCOL_TAG, protocol)
        return ResourceSpec(ts_class, kwargs)

    @classmethod
    def is_running_with_auth(cls, host_name: str, port: int = None) -> tuple:   # -- (is_running, with_auth)
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

    @abc.abstractmethod
    def db_name(self) -> str: ...

    @abc.abstractmethod
    def add_who(self, field: str, serialized_data: dict) -> dict: ...

    @abc.abstractmethod
    def add_when(self, field: str, serialized_data: dict) -> dict: ...

    @abc.abstractmethod
    def server_time(self) -> datetime: ...

    def supports_transactions(self) -> bool:
        return True

    def copy_to(self, to_store: TsStore, overwrite: bool = False) -> RC:
        """Copy all collections from this store to another store."""
        rc = RC(True)

        for collection_name in self.collection_names():
            from_coll = self.collection(collection_name)
            to_coll = to_store.collection(collection_name)
            rc += from_coll.copy_to(to_coll, overwrite=overwrite)

        return rc

    @contextmanager
    def transaction(self):
        """Context manager for transactional operations. Yields a transaction object with commit() and abort()."""
        tx = self.Transaction(self)
        success = False
        try:
            yield tx
            success = True
        finally:
            if success:
                tx.commit()
            else:
                tx.abort()



@contextmanager
def SaveIfChanged(classes: Sequence[type[Traitable]] = ()):  # noqa: N802
    if any(not cls.is_storable() for cls in classes):
        raise RuntimeError('Classes passed to SaveIfChanged must be storable.')

    if not isinstance(classes,tuple):
        classes = tuple(classes)

    tracker = BTPTracker()
    tracker.begin_using()
    yield tracker
    tracker.end_using()

    tracked = tuple(traitable for traitable in tracker.tracked_objects() if traitable.is_storable())

    with ExitStack() as tx_stack:
        if EnvVars.use_ts_store_transactions:
            for store in {cls.store() for cls in classes or tuple({traitable.__class__ for traitable in tracked})}:
                tx_stack.enter_context(store.transaction())

        for traitable in tracked:
            if not classes or isinstance(traitable, classes):
                traitable.save().throw()
