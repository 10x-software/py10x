import abc
from collections.abc import Iterable
from typing import Self

from core_10x.exec_control import ProcessContext
from core_10x.global_cache import standard_key
from core_10x.py_class import PyClass
from core_10x.resource import TS_STORE, Resource
from core_10x.trait_filter import f


class TsCollection(abc.ABC):
    s_id_tag: str = None

    @abc.abstractmethod
    def id_exists(self, id_value: str) -> bool: ...
    @abc.abstractmethod
    def find(self, query: f = None, _at_most: int = 0, _order: dict = None) -> Iterable: ...
    @abc.abstractmethod
    def count(self, query: f = None) -> int: ...
    @abc.abstractmethod
    def save_new(self, serialized_traitable: dict) -> int: ...
    @abc.abstractmethod
    def save(self, serialized_traitable: dict) -> int:  ...
    @abc.abstractmethod
    def delete(self, id_value: str) -> bool: ...
    @abc.abstractmethod
    def create_index(self, name: str, trait_name: str, **index_args) -> str: ...
    @abc.abstractmethod
    def max(self, trait_name: str, filter: f = None) -> dict: ...
    @abc.abstractmethod
    def min(self, trait_name: str, filter: f = None) -> dict: ...

    def exists(self, query: f) -> bool:
        return self.count(query) > 0

    def load(self, id_value: str) -> dict:
        for data in self.find(f(**{self.s_id_tag: id_value})):
            return data

class TsStore(Resource, resource_type = TS_STORE):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        assert cls.__mro__[1] is TsStore, 'TsStore must be the first base class'
        cls.s_instance_kwargs_map = { **TsStore.s_instance_kwargs_map, **cls.s_instance_kwargs_map }

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
    def instance(cls, *args, password = '', _cache = True, **kwargs) -> Self:
        translated_kwargs = cls.translate_kwargs(kwargs)
        try:
            if not _cache:
                return cls.new_instance(*args, password = password, **translated_kwargs)

            instance_key = cls.standard_key(*args, **kwargs)
            store = cls.s_instances.get(instance_key)
            if not store:
                store = cls.new_instance(*args, password = password, **translated_kwargs)
                cls.s_instances[instance_key] = store

            return store

        except Exception as e:
            raise OSError(f'Failed to connect to {cls.s_driver_name}({args}, {translated_kwargs})\nOriginal Exception:\n{e!s}') from e

    s_instance_kwargs_map = {
        Resource.HOSTNAME_TAG:  (Resource.HOSTNAME_TAG, None),
        Resource.USERNAME_TAG:  (Resource.USERNAME_TAG, None),
        Resource.DBNAME_TAG:    (Resource.DBNAME_TAG,   None),
        Resource.PORT_TAG:      (Resource.PORT_TAG,     None),
        Resource.SSL_TAG:       (Resource.SSL_TAG,      True),
        'sst':                  ('sst',                 1000),
    }

    @classmethod
    def translate_kwargs(cls, kwargs: dict) -> dict:
        kwargs_map = cls.s_instance_kwargs_map
        def_kwargs = { name: def_value for name, (real_name, def_value) in kwargs_map.items() }
        def_kwargs.update(kwargs)
        return { kwargs_map[name][0]: value for name, value in def_kwargs.items() }

    @classmethod
    def new_instance(cls, *args, password: str, **kwargs) -> 'TsStore':
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

    @classmethod
    def is_running_with_auth( cls, host_name: str ) -> tuple:  ...    #-- (is_running, with_auth)
