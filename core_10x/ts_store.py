from typing import Iterable

from core_10x.trait_filter import f
from core_10x.rc import RC
from core_10x.py_class import PyClass
from core_10x.global_cache import standard_key

class TsCollection:
    s_id_tag: str = None

    def find(self, query: f = None) -> Iterable:                                raise NotImplementedError
    def save_new(self, serialized_traitable: dict) -> int:                      raise NotImplementedError
    def save(self, serialized_traitable: dict) -> RC:                           raise NotImplementedError
    def delete(self, id_value: str) -> bool:                                    raise NotImplementedError

    def create_index(self, name: str, trait_name: str, **index_args) -> str:    raise NotImplementedError
    def max(self, trait_name: str, filter: f = None) -> dict:                   raise NotImplementedError
    def min(self, trait_name: str, filter: f = None) -> dict:                   raise NotImplementedError

    def exists(self, query: f) -> bool:
        return bool(self.find(query))

    def load(self, id_value: str) -> dict:
        cur = self.find(f(**{self.s_id_tag: id_value}))
        for data in cur:
            return data
        return None

class TsStore:
    s_default_port = None

    @staticmethod
    def store_class(store_class_name: str):
        cls = PyClass.find(store_class_name, TsStore)
        assert cls, f'Unknown TsStore class {store_class_name}'
        return cls

    s_instances = {}
    @classmethod
    def instance(cls, hostname: str, dbname: str, username: str, password: str, _cache = True, **kwargs) -> 'TsStore':
        translated_kwargs = cls.translate_kwargs(kwargs)
        if not _cache:
            return cls.new_instance(hostname, dbname, username, password, **translated_kwargs)

        instance_key = standard_key((hostname, username, dbname), kwargs)
        store = cls.s_instances.get(instance_key)
        if not store:
            store = cls.new_instance(hostname, dbname, username, password, **translated_kwargs)
            cls.s_instances[instance_key] = store

        return store

    s_instance_kwargs_map = dict(
        port    = ('port',  None),
        ssl     = ('ssl',   True),
        sst     = ('sst',   1000),
    )
    @classmethod
    def translate_kwargs(cls, kwargs: dict) -> dict:
        kwargs_map = cls.s_instance_kwargs_map
        def_kwargs = { name: def_value for name, (real_name, def_value) in kwargs_map.items() }
        def_kwargs.update(kwargs)
        return { kwargs_map[name][0]: value for name, value in def_kwargs.items() }

    @classmethod
    def new_instance(cls, hostname: str, dbname: str, username: str, password: str, **kwargs) -> 'TsStore':
        raise NotImplementedError

    def collection_names(self, regexp: str = None) -> list:                     raise NotImplementedError
    def collection(self, collection_name: str) -> TsCollection:                 raise NotImplementedError
    def delete_collection(self, collection_name: str) -> bool:                    raise NotImplementedError
