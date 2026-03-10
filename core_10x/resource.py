from __future__ import annotations

import abc
import inspect
from collections import deque
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

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

    # def __call__(self, *args, **kwargs):
    #     return ResourceRequirements(self, *args, **kwargs)

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

    def hostname(self) -> str:
        return self.kwargs[Resource.HOSTNAME_TAG]

    def set_credentials(self, username: str = None, password: str = None):
        if username is not None:
            self.kwargs[self.resource_class.USERNAME_TAG] = username
        if password is not None:
            self.kwargs[self.resource_class.PASSWORD_TAG] = password

    def uri(self) -> str:
        kwargs = dict(self.kwargs)
        protocol = kwargs.pop(Resource.PROTOCOL_TAG, None)
        if not protocol:
            raise ValueError('URI protocol is missing.')

        username = kwargs.pop(Resource.USERNAME_TAG, None)
        password = kwargs.pop(Resource.PASSWORD_TAG, None)
        userinfo = ''
        if username:
            userinfo = quote(username, safe='')
            if password:
                userinfo += f':{quote(password, safe="")}'
            userinfo += '@'

        host_netloc = kwargs.pop(Resource.NETLOC_TAG, None)
        if host_netloc is None:     #-- kwargs were constructed manually, not via parse_uri
            host = kwargs.pop(Resource.HOSTNAME_TAG, '')
            port = kwargs.pop(Resource.PORT_TAG, None)
            host_netloc = f'{host}:{port}' if port else host
        else:
            kwargs.pop(Resource.HOSTNAME_TAG, None)
            kwargs.pop(Resource.PORT_TAG, None)

        dbname   = kwargs.pop(Resource.DBNAME_TAG, None)
        query    = kwargs.pop(Resource.QUERY_TAG, '')
        fragment = kwargs.pop(Resource.FRAGMENT_TAG, '')
        if kwargs:
            extra = urlencode(kwargs, doseq=True)
            query = f'{query}&{extra}' if query else extra

        #-- always emit '//' so empty-netloc URIs like duckdb:// or duckdb:///path round-trip correctly;
        #-- urlunsplit drops '//' for unknown schemes when netloc is empty
        netloc = userinfo + host_netloc
        path   = f'/{dbname}' if dbname else ''
        url    = f'{protocol}://{netloc}{path}'
        if query:    url += f'?{query}'
        if fragment: url += f'#{fragment}'
        return url

class Resource(abc.ABC):
    PROTOCOL_TAG    = 'protocol'
    NETLOC_TAG      = 'netloc'      #-- host+port portion of netloc, as formatted by urlsplit (IPv6 brackets preserved)
    HOSTNAME_TAG    = 'hostname'
    PORT_TAG        = 'port'
    USERNAME_TAG    = 'username'
    DBNAME_TAG      = 'dbname'
    PASSWORD_TAG    = 'password'
    QUERY_TAG       = 'query'
    FRAGMENT_TAG    = 'fragment'
    SSL_TAG         = 'ssl'

    s_resource_type: ResourceType = None
    s_driver_name: str = None

    @classmethod
    def parse_uri(cls, uri: str) -> dict:
        try:
            parts = urlsplit(uri)
            if not parts.scheme:
                raise ValueError(f'Invalid URI = {uri}')

            kwargs = {
                cls.PROTOCOL_TAG: parts.scheme,
                cls.NETLOC_TAG:   parts.netloc.split('@', 1)[-1],   #-- strip userinfo; urlsplit already formatted host (IPv6 brackets etc.)
                cls.USERNAME_TAG: parts.username,
                cls.PASSWORD_TAG: parts.password,
            }

            if parts.hostname is not None:
                kwargs[cls.HOSTNAME_TAG] = parts.hostname
            if parts.port is not None:
                kwargs[cls.PORT_TAG] = parts.port

            db_name = parts.path.lstrip('/')
            if db_name:
                kwargs[cls.DBNAME_TAG] = db_name
            if parts.query:
                kwargs[cls.QUERY_TAG] = parts.query
            if parts.fragment:
                kwargs[cls.FRAGMENT_TAG] = parts.fragment

            return kwargs
        except Exception as e:
            raise ValueError(f'Invalid URI = {uri}') from e

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
    def spec_from_uri(cls, uri: str) -> ResourceSpec:
        return ResourceSpec(cls, cls.parse_uri(uri))

    @classmethod
    @abc.abstractmethod
    def instance(cls, *args, **kwargs) -> Resource: ...

    @abc.abstractmethod
    def on_enter(self): ...

    @abc.abstractmethod
    def on_exit(self): ...

class NullResource:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

NULL_RESOURCE = NullResource()

#=========== Known Resource Types
TS_STORE        = ResourceType('TS_STORE')
REL_DB          = ResourceType('REL_DB')
CLOUD_CLUSTER   = ResourceType('CLOUD_CLUSTER')
