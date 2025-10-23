from __future__ import annotations

import heapq
import itertools
import operator
from itertools import zip_longest
from typing import TYPE_CHECKING

from core_10x.nucleus import Nucleus
from core_10x.trait_filter import EQ, f
from core_10x.ts_store import TsCollection, TsStore

if TYPE_CHECKING:
    from collections.abc import Iterable


class _OrderKey:
    __slots__ = ('reverse', 'value')

    @classmethod
    def _dict_cmp(cls, d: dict, od: dict) -> int:
        assert isinstance(od, dict), 'can only compare dict to dict'

        for i, oi in zip_longest(d.items(), od.items()):
            if i == oi:
                continue
            if i is None:
                return -1  # all match, d is shorter
            if oi is None:
                return 1  # all match d is longer
            k, v = i
            ok, ov = oi
            if k != ok:
                return -1 if k < ok else 1 if k > ok else 0  # keys do not match
            if isinstance(v, dict) and isinstance(ov, dict):
                return cls._dict_cmp(v, ov)
            # TODO: handle mismatching types..
            return -1 if v < ov else 1 if v > ov else 0
        return 0  # equals..

    def __init__(self, value, reverse: bool):
        self.value = value
        self.reverse = reverse

    def __lt__(self, other):
        assert isinstance(other, _OrderKey), 'can only compare to order key'
        v = self.value
        ov = other.value
        if isinstance(v, dict):
            return self._dict_cmp(v, ov) < 0 if self.reverse else self._dict_cmp(ov, v) > 0
        return ov < v if self.reverse else v < ov

    def __eq__(self, other):
        assert isinstance(other, _OrderKey), 'can only compare to order key'
        v = self.value
        ov = other.value
        return not self._dict_cmp(v, ov) if isinstance(v, dict) else v == ov

    @classmethod
    def key(cls, item, order):
        return tuple(cls(value=item.get(k), reverse=v < 0) for k, v in order)


class TsUnionCollection(TsCollection):
    def __init__(self, *collections: TsCollection):
        self.collections = collections

    def find(self, query: f = None, _at_most: int = 0, _order: dict = None) -> Iterable:
        order = tuple((_order or {'_id': 1}).items())  # FIX: assumes _id is always there!
        order_key = _OrderKey.key
        iterables = (collection.find(query, _at_most=_at_most, _order=_order) for collection in self.collections)
        keyed_iterables = (((order_key(item, order), item) for item in iterable) for iterable in iterables if iterable is not None)
        results = (item for _, item in heapq.merge(*keyed_iterables, key=operator.itemgetter(0)))
        return (item for i, item in enumerate(results) if i < _at_most) if _at_most else results

    def save_new(self, serialized_traitable):
        return self.collections[0].save_new(serialized_traitable)

    def save(self, serialized_traitable):
        # if serialized_traitable was not loaded from the union head, we need to call save_new
        id_tag = Nucleus.ID_TAG()
        if not self.collections[0].exists(f(**{id_tag: EQ(serialized_traitable[id_tag])})):
            # TODO: optimize by introducing save with overwrite flag to bypass the "inappropriate restore from deleted" check
            return self.collections[0].save_new(serialized_traitable)
        return self.collections[0].save(serialized_traitable)

    def delete(self, id_value):
        # if id_value exists in the union tail, return False as the object wasn't fully deleted
        return self.collections[0].delete(id_value) and not self.exists(f(**{Nucleus.ID_TAG(): EQ(id_value)}))

    def create_index(self, name, trait_name, **index_args):
        # TODO: verify that index exists in the union tail
        return self.collections[0].create_index(name, trait_name, **index_args)

    def max(self, trait_name: str, filter: f = None) -> dict:
        results = (result for result in (collection.max(trait_name, filter) for collection in self.collections) if result is not None)
        return max(results, key=operator.itemgetter(trait_name), default=None)

    def min(self, trait_name: str, filter: f = None) -> dict:
        results = (result for result in (collection.min(trait_name, filter) for collection in self.collections) if result is not None)
        return min(results, key=operator.itemgetter(trait_name), default=None)

    def id_exists(self, id_value: str) -> bool:
        return any(collection.id_exists(id_value) for collection in self.collections)

    def count(self, query: f = None) -> int:
        return sum(collection.count(query) for collection in self.collections)

    def load(self, id_value: str) -> dict | None:
        for collection in self.collections:
            data = collection.load(id_value)
            if data is not None:
                return data
        return None


class TsUnion(TsStore, resource_name='TS_UNION'):
    @classmethod
    def is_running_with_auth(cls, host_name: str) -> tuple:  # -- (is_running, with_auth)
        raise NotImplementedError

    @classmethod
    def standard_key(cls, *args) -> tuple:
        return tuple(cls.s_resource_type.resource_driver(kw['driver_name']).standard_key(**kw) for kw in args)

    @classmethod
    def new_instance(cls, *args, **kwargs) -> TsUnion:
        stores = [cls.s_resource_type.resource_driver(kw.pop('driver_name')).instance(**kw) for kw in args]
        return TsUnion(*stores)

    def __init__(self, *stores: TsStore):
        self.stores = stores

    def collection_names(self, regexp: str = None) -> list:
        return list(set(itertools.chain(*(store.collection_names(regexp) for store in self.stores))))

    def collection(self, collection_name):
        return TsUnionCollection(*(store.collection(collection_name) for store in self.stores))

    def delete_collection(self, collection_name: str) -> bool:
        return self.stores[0].delete_collection(collection_name) if self.stores else False

    def auth_user(self) -> str | None:
        return self.stores[0].auth_user() if self.stores else None
