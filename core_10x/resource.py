from __future__ import annotations

import abc
import inspect
from collections import deque

#-- TODO: move to attic
# class ResourceRequirements:
#     def __init__(self, resource_type, *args, **kwargs):
#         self.domain = None
#         self.category: str = None
#         self.resource_type = resource_type
#         self.args = args
#         self.kwargs = kwargs
#
#
# class ResourceBinding:
#     def __init__(
#         self, _resource_class: type = None, _resource_type: ResourceType = None, _resource_name: str = None, _driver_name: str = None, **kwargs
#     ):
#         if _resource_class:
#             assert issubclass(_resource_class, Resource), f'{_resource_class} is not a subclass of Resource'
#         else:
#             if _resource_name:
#                 _resource_type = ResourceType.instance(_resource_name)
#             else:
#                 assert _resource_type and isinstance(_resource_type, ResourceType), '_resource_type must be an instance of ResourceType'
#
#             _resource_class = _resource_type.resource_drivers.get(_driver_name)
#             assert _resource_class, f'Unknown _driver_name {_driver_name}'
#
#         self.resource_class = _resource_class
#         self.kwargs = kwargs
#
#
# R = ResourceBinding
#

class ResourceType:
    s_dir = {}

    def __init__(self, name: str):
        xrt = self.s_dir.get(name)
        assert xrt is None, f"Resource type '{name}' has already been created"
        self.s_dir[name] = xrt

        self.name = name
        self.resource_stack = deque()
        self.resource_drivers = {}

    def __call__(self, *args, **kwargs):
        return ResourceRequirements(self, *args, **kwargs)

    def __getattr__(self, driver_name: str):
        return self.resource_drivers.get(driver_name)

    @staticmethod
    def instance(name: str, throw: bool = True):
        rt = ResourceType.s_dir.get(name)
        if not rt and throw:
            raise ValueError(f"Unknown Resource type '{name}'")

        return rt

    def register_driver(self, name: str, driver_class):
        existing_driver = self.resource_drivers.get(name)
        assert not existing_driver, f"Resource '{name}' is already registered in {existing_driver}"
        assert inspect.isclass(driver_class) and issubclass(driver_class, Resource), 'driver_class must be a subclass of Resource'
        self.resource_drivers[name] = driver_class

    def resource_driver(self, name: str, throw: bool = True):
        r = self.resource_drivers.get(name)
        if not r and throw:
            raise ValueError(f"Unknown resource '{name}'")

        return r

    def begin_using(self, resource, last: bool = True):
        self.resource_stack.append(resource) if last else self.resource_stack.appendleft(resource)

    def end_using(self):
        self.resource_stack.pop()  # -- will throw if begin_using() hasn't been called

    def current_resource(self):
        stack = self.resource_stack
        return stack[-1] if stack else None


class ResourceSpec:
    def __init__(self, resource_class, kwargs: dict):
        self.resource_class = resource_class
        self.kwargs = kwargs

    def set_credentials(self, username: str = None, password: str = None):
        if username is not None:
            self.kwargs[self.resource_class.USERNAME_TAG] = username
        if password is not None:
            self.kwargs[self.resource_class.PASSWORD_TAG] = password

class Resource(abc.ABC):
    HOSTNAME_TAG    = 'hostname'
    PORT_TAG        = 'port'
    USERNAME_TAG    = 'username'
    DBNAME_TAG      = 'dbname'
    PASSWORD_TAG    = 'password'
    SSL_TAG         = 'ssl'

    s_resource_type: ResourceType = None
    s_driver_name: str = None

    def __init_subclass__(cls, resource_type: ResourceType = None, resource_name: str = None, **kwargs):
        if cls.s_resource_type is None:     #-- must be a top class of a particular resource type, e.g. TsStore
            assert resource_type and isinstance(resource_type, ResourceType), 'instance of ResourceType is expected'
            assert resource_name is None, f'May not define Resource name for top class of Resource Type: {resource_type}'
            cls.s_resource_type = resource_type

        else:   #-- a Resource of a particular resource type
            assert resource_type is None, f'resource_type is already set: {cls.s_resource_type}'
            assert resource_name and isinstance(resource_name, str), 'a unique Resource name is expected'
            cls.s_resource_type.register_driver(resource_name, cls)
            cls.s_driver_name = resource_name

    def __enter__(self):
        return self.begin_using()

    def __exit__(self, *args):
        self.end_using()

    def begin_using(self):
        rt = self.__class__.s_resource_type
        rt.begin_using(self)
        self.on_enter()
        return rt

    def end_using(self):
        self.__class__.s_resource_type.end_using()
        self.on_exit()

    @classmethod
    def instance_from_uri(cls, uri: str, username: str = None, password: str = None) -> Resource:
        spec = cls.spec_from_uri(uri)
        spec.set_credentials(username=username, password=password)
        return spec.resource_class.instance(**spec.kwargs)

    @classmethod
    @abc.abstractmethod
    def spec_from_uri(cls, uri: str) -> ResourceSpec: ...

    @classmethod
    @abc.abstractmethod
    def instance(cls, *args, **kwargs) -> Resource: ...

    @abc.abstractmethod
    def on_enter(self): ...

    @abc.abstractmethod
    def on_exit(self): ...


#=========== Known Resource Types
TS_STORE        = ResourceType('TS_STORE')
REL_DB          = ResourceType('REL_DB')
CLOUD_CLUSTER   = ResourceType('CLOUD_CLUSTER')
