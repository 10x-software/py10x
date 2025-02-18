import itertools
import operator
from typing import List, Self, Iterable

from core_10x.nucleus import Nucleus
from core_10x.trait_filter import f, EQ
from core_10x.ts_store import TsStore, TsCollection


class TsUnionCollection(TsCollection):
    def __init__(self, *collections: TsCollection):
        self.collections = collections

    def find(self, query: f = None) -> Iterable:
        results = (result for result in (collection.find(query) for collection in self.collections) if result is not None)
        return itertools.chain.from_iterable(results) #TODO: merge iterables using sorted order (default by _id, but later as specified by the user)

    def save_new(self, serialized_traitable):
        return self.collections[0].save_new(serialized_traitable)

    def save(self, serialized_traitable):
        #if serialized_traitable was not loaded from the union head, we need to call save_new
        if not self.collections[0].exists(f(**{Nucleus.ID_TAG: EQ(serialized_traitable[Nucleus.ID_TAG])})):
            #TODO: optimize by introducing save with overwrite flag to bypass the "inappropriate restore from deleted" check
            return self.collections[0].save_new(serialized_traitable)
        return self.collections[0].save(serialized_traitable)

    def delete(self, id_value):
        #if id_value exists in the union tail, return False as the object wasn't fully deleted
        return self.collections[0].delete(id_value) and not self.exists(f(**{Nucleus.ID_TAG: EQ(id_value)}))

    def create_index(self, name, trait_name, **index_args):
        #TODO: verify that index exists in the union tail
        return self.collections[0].create_index(name, trait_name, **index_args)

    def max(self, trait_name: str, filter: f = None) -> dict:
        results = (result for result in (collection.max(trait_name, filter) for collection in self.collections) if result is not None)
        return max(results,key=operator.itemgetter(trait_name),default=None)

    def min(self, trait_name: str, filter: f = None) -> dict:
        results = (result for result in (collection.min(trait_name, filter) for collection in self.collections) if result is not None)
        return min(results,key=operator.itemgetter(trait_name),default=None)


class TsUnion(TsStore, name='TS_UNION'):
    @classmethod
    def translate_kwargs(cls, kwargs: dict) -> dict:
        return kwargs

    @classmethod
    def new_instance(cls, hostname: str, dbname: str, username: str, password: str, store_class: str='', **kwargs) -> Self:
        hostnames = hostname.split(':')
        dbnames = dbname.split(':')
        usernames = username.split(':')
        passwords = password.split(':')
        store_class_names = store_class.split(':')
        assert len(hostnames) == len(dbnames) == len(usernames) == len(passwords) == len(store_class_names), 'All parameters must have the same number of values'
        assert all(isinstance(v,(list,tuple)) and len(v)==len(hostnames) for v in kwargs.values()), 'All keyword arguments must have the same number of values'

        store_classes = [cls.s_resource_type.resource_driver(store_class_name) for store_class_name in store_class_names]
        stores = [store_class.instance(hostname, dbname, username, password, **{k:v[i] for k,v in kwargs.items()})
                  for i, (hostname, dbname, username, password, store_class)
                  in enumerate(zip(hostnames, dbnames, usernames, passwords, store_classes))]

        return TsUnion(*stores)

    def __init__(self, *stores: TsStore):
        self.stores = stores

    def collection_names(self, regexp: str = None) -> list:
        return list(set(itertools.chain(*(store.collection_names(regexp) for store in self.stores))))

    def collection(self, collection_name):
        return TsUnionCollection(*(store.collection(collection_name) for store in self.stores))

    def delete_collection(self, collection_name: str) -> bool:
        return self.stores[0].delete_collection(collection_name)