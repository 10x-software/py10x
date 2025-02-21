import abc
import inspect
from collections import deque

#===================================================================================================================================
#   We'd like to do the following:
#
#   class MongodbStore(Resource, resource_type = TS_STORE, name = 'MONGO'):
#       ...
#
#   class RayCluster(Resource, resource_type = CLOUD_CLUSTER, name = 'RAY_CLUSTER'):
#       ...
#
#   class MDU(DataDomain):
#       GENERAL             = TS_STORE()            #-- ResourceRequirements
#       SYMBOLOGY           = REL_DB()              #--
#       MKT_CLOSE_CLUSTER   = CLOUD_CLUSTER(...)    #--
#
#   DataDomainBinder('MDU',
#       GENERAL             = R('TS_STORE',         'MONGO',        'dev.mongo.general.io', tsl = True)
#       SYMBOLOGY           = R('REL_DB',           'ORACLE',       'dev.oracle.io', a = '...', b = '...')
#       MKT_CLOSE_CLUSTER   = R('CLOUD_CLUSTER',    'RAY_CLUSTER',  'dev.ray1.io', ...)
#   )
#
#===================================================================================================================================

class ResourceRequirements:
    def __init__(self, resource_type, *args, **kwargs):
        self.resource_type = resource_type
        self.args = args
        self.kwargs = kwargs

class ResourceBinding:
    def __init__(self, resource_type_or_name, resource_name: str, *args, **kwargs):
        if isinstance(resource_type_or_name, str):
            self.resource_type = ResourceType.instance(resource_type_or_name)
        else:
            assert isinstance(resource_type_or_name, ResourceType), 'instance of ResourceType is expected'
            self.resource_type = resource_type_or_name

        self.resource_name = resource_name
        self.args = args
        self.kwargs = kwargs
R = ResourceBinding

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

    @staticmethod
    def instance(name: str, throw = True) -> 'ResourceType':
        rt = ResourceType.s_dir.get(name)
        if not rt and throw:
            raise ValueError(f"Unknown Resource type '{name}'")

        return rt

    def register_driver(self, name: str, driver_class):
        existing_driver = self.resource_drivers.get(name)
        assert not existing_driver, f"Resource '{name}' is already registered in {existing_driver}"
        assert inspect.isclass(driver_class) and issubclass(driver_class, Resource), 'driver_class must be a subclass of Resource'
        self.resource_drivers[name] = driver_class

    def resource_driver(self, name: str, throw = True):
        r = self.resource_drivers.get(name)
        if not r and throw:
            raise ValueError(f"Unknown resource '{name}'")

        return r

    def begin_using(self, resource, last = True):
        self.resource_stack.append(resource) if last else self.resource_stack.appendleft(resource)

    def end_using(self):
        self.resource_stack.pop()       #-- will throw if begin_using() hasn't been called

    def current_resource(self):
        stack = self.resource_stack
        return stack[-1] if stack else None

class Resource(abc.ABC):
    s_resource_type: ResourceType = None
    def __init_subclass__(cls, resource_type: ResourceType = None, name: str = None):
        if cls.s_resource_type is None:   #-- must be a top class of a particular resource type, e.g. TsStore
            assert resource_type and isinstance(resource_type, ResourceType), 'instance of ResourceType is expected'
            assert name is None, f'May not define Resource name for top class of Resource Type: {resource_type}'
            cls.s_resource_type = resource_type

        else:   #-- a Resource of a particular resource type
            assert resource_type is None, f'resource_type is already set: {cls.s_resource_type}'
            assert name and isinstance(name, str), 'a unique Resource name is expected'
            cls.s_resource_type.register_driver(name, cls)

    def __enter__(self):
        rt = self.__class__.s_resource_type
        rt.begin_using(self)
        self.on_enter()
        return rt

    def __exit__(self,*args):
        self.__class__.s_resource_type.end_using()
        self.on_exit()

    @abc.abstractmethod
    def on_enter(self): ...

    @abc.abstractmethod
    def on_exit(self): ...

#=========== Known Resource Types

TS_STORE        = ResourceType('TS_STORE')
REL_DB          = ResourceType('REL_DB')
CLOUD_CLUSTER   = ResourceType('CLOUD_CLUSTER')

