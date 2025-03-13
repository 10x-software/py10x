import inspect
import operator
from functools import reduce
from itertools import chain

from core_10x_i import BTraitable, BTraitableClass

from core_10x.nucleus import Nucleus
from core_10x.xnone import XNone
from core_10x.trait_definition import TraitDefinition, TraitModification, RT, M, Ui
from core_10x.trait import Trait, TRAIT_METHOD, T, BoundTrait, trait_value
import core_10x.concrete_traits as concrete_traits
from core_10x.global_cache import cache
from core_10x.rc import RC, RC_TRUE
from core_10x.package_refactoring import PackageRefactoring
from core_10x.ts_store import TS_STORE, TsStore, TsCollection
from core_10x.package_manifest import PackageManifest
from core_10x.resource import ResourceRequirements
from core_10x.trait_filter import f


class TraitAccessor:
    __slots__ = ('cls', 'obj')
    def __init__(self, obj: 'Traitable'):
        self.cls = obj.__class__
        self.obj = obj

    def __getattr__(self, trait_name: str) -> BoundTrait:
        trait = self.cls.trait(trait_name, throw = True)
        return BoundTrait(self.obj, trait)

    def __call__(self, trait_name: str, throw = True) -> Trait:
        return self.cls.trait(trait_name, throw = True)

class TraitableMetaclass(type(BTraitable)):
    @staticmethod
    def find_symbols(bases,class_dict,symbol):
        return chain(
            filter(None,(class_dict.get(symbol),)),
            (res for base in bases if (res := getattr(base,symbol,None)))
        )

    @staticmethod
    @cache
    def rev_trait() -> Trait:
        trait_name = Nucleus.REVISION_TAG
        t_def = T(0, T.RESERVED)
        return Trait.create(trait_name, t_def, {}, {trait_name: int},  RC_TRUE)

    def __new__(cls, name, bases, class_dict, **kwargs):
        build_trait_dir = next(cls.find_symbols(bases,class_dict,'build_trait_dir'))
        special_attributes = tuple(chain.from_iterable(cls.find_symbols(bases,class_dict,'s_special_attributes')))
        trait_dir = {Nucleus.REVISION_TAG: cls.rev_trait()}                #-- insert _rev as the first trait and delete later if not needed
        build_trait_dir(bases, class_dict, trait_dir).throw(exc=TypeError)  #-- build trait dir_from trait definitions in class_dict

        for item in trait_dir:
            if item in class_dict:
                del class_dict[item]                                        #-- delete trait names from class_dict as they will be in __slots__
        class_dict.update(
            s_dir = trait_dir,
            __slots__ = ( *special_attributes, *tuple(trait_dir.keys()) ),
            s_special_attributes = special_attributes
        )

        return super().__new__(cls, name, bases, class_dict, **kwargs)

class Traitable(BTraitable, Nucleus, metaclass=TraitableMetaclass):
    s_dir = {}
    @staticmethod
    def build_trait_dir(bases, class_dict, trait_dir) -> RC:
        annotations = class_dict.get('__annotations__') or {}

        rc = RC(True)
        trait_dir |= reduce(operator.or_, TraitableMetaclass.find_symbols(bases,class_dict,'s_dir'), {}) #-- shallow copy!

        for trait_name, old_trait in trait_dir.items():
            if any(func_name in class_dict for func_name in Trait.method_defs(trait_name)):
                t_def =old_trait.t_def
                trait_dir[trait_name] = Trait.create(trait_name, t_def, class_dict, {trait_name:t_def.data_type} | annotations, rc)

        for trait_name, trait_def in class_dict.items():
            if not isinstance(trait_def, TraitDefinition):
                continue

            dt = annotations.get(trait_name, XNone.__class__)
            if isinstance(trait_def, TraitModification):
                old_trait: Trait = trait_dir.get(trait_name)
                if not old_trait:
                    rc <<= f'{trait_name} = M(...), but the trait is unknown'

                trait_def = trait_def.apply(old_trait.t_def)
                if dt is not XNone:     #-- the data type is also being modified
                    trait_def.data_type = dt

            else:
                trait_def.data_type = dt

            trait_def.name = trait_name
            trait_dir[trait_name] = Trait.create(trait_name, trait_def, class_dict, annotations, rc)
        return rc

    @classmethod
    def trait(cls, trait_name: str, throw = False) -> Trait:
        trait = cls.s_dir.get(trait_name)
        if trait is None and throw:
            raise TypeError(f'{cls} - unknown trait {trait_name}')

        return trait

    @classmethod
    def is_id_endogenous(cls) -> bool:
        return cls.s_bclass.is_id_endogenous()

    @classmethod
    def is_storable(cls) -> bool:
        return cls.s_bclass.is_storable()

    @staticmethod
    def find_storable_class(class_id: str):
        traitable_class = PackageRefactoring.find_class(class_id)
        if not issubclass(traitable_class, Traitable) or not traitable_class.is_storable():
            raise TypeError(f'{traitable_class} is not a storable Traitable')

        return traitable_class

    s_bclass: BTraitableClass = None
    s_traitdef_dir = {}
    s_special_attributes = (
        'T',
        '_default_cache',
    )
    def __init_subclass__(cls, **kwargs):

        cls.s_bclass = BTraitableClass(cls)

        if not cls.is_storable():
            del cls.s_dir[Nucleus.REVISION_TAG]
            cls.collection = lambda: None
            cls.exists_in_store = lambda id: False
            cls.load_data = lambda id_value: None
            cls.load = lambda id_value: None
            cls.load_many = lambda query: []
            cls.load_ids = lambda query: []
            cls.save = lambda self: RC(False, f'{cls} is not storable')

        for trait_name, trait in cls.s_dir.items():
            setattr(cls, trait_name, trait)


    @classmethod
    def instance_by_id(cls, id_value: str) -> 'Traitable':
        if not cls.s_bclass.known_object(id_value):
            return cls.load(id_value)

        return cls(_id = id_value)

    def __init__(self, _id: str = None, **trait_values):
        super().__init__(self.s_bclass)

        if _id is not None:
            assert not trait_values, f'{self.__class__}(id_value) may not be invoked with trait_values'
            self.set_id(_id)
        else:
            self.initialize(**trait_values)

        self.T = TraitAccessor(self)

    def set_values(self, _ignore_unknown_traits = True, **trait_values) -> RC:
        return self._set_values(trait_values, _ignore_unknown_traits)

    #===================================================================================================================
    #   The following methods are available from c++
    #
    #   get_value(trait-or-name, *args) -> Any
    #   set_value(trait-or_name, value: Any, *args) -> RC
    #   raw_value(trait-or_name, value: Any, *args) -> RC
    #   invalidate_value(trait-or-name)
    #===================================================================================================================

    #===================================================================================================================
    #   Nucleus related methods
    #===================================================================================================================

    #-- serialize() is defined in BTraitable

    @classmethod
    def serialized_class(cls, serialized_data: dict):
        return cls

    @classmethod
    def deserialize(cls, serialized_data) -> 'Traitable':
        return cls.s_bclass.deserialize(serialized_data)

    def to_str(self) -> str:
        return f'{self.id()}'

    @classmethod
    def from_str(cls, s: str) -> Nucleus:
        return cls.instance_by_id(s)

    @classmethod
    def from_any_xstr(cls, value) -> Nucleus:
        if isinstance(value, dict):
            return cls(**value)

        raise TypeError(f'{cls}.from_any_xstr() expects a dict, got {value})')

    @classmethod
    def same_values(cls, value1, value2) -> bool:
        return value1.id() == value2.id()

    #===================================================================================================================
    #   Storage related methods
    #===================================================================================================================

    @staticmethod
    @cache
    def _bound_data_domain(domain):
        from core_10x.backbone.bound_data_domain import BoundDataDomain

        bbd = BoundDataDomain(domain = domain)
        if bbd:
            bbd.reload()
        return bbd

    @classmethod
    @cache
    def preferred_store(cls) -> TsStore:
        rr = PackageManifest.resource_requirements(cls)
        if not rr:
            return None

        bbd = Traitable._bound_data_domain(rr.domain)
        return bbd.resource(rr.category, throw = False) if bbd else None

    @classmethod
    def store(cls) -> TsStore:
        store: TsStore = TS_STORE.current_resource()
        if not store:
            store = cls.preferred_store()
            if not store:
                raise EnvironmentError(f'{cls} - failed to find a store')

        return store

    @classmethod
    def collection(cls) -> TsCollection:
        store = cls.store()
        cname = PackageRefactoring.find_class_id(cls)
        return store.collection(cname)

    @classmethod
    def exists_in_store(cls, id_value: str) -> bool:
        coll = cls.collection()
        return coll.id_exists(id_value)

    @classmethod
    def load_data(cls, id_value: str) -> dict:
        coll = cls.collection()
        return coll.load(id_value)

    @classmethod
    def load(cls, id_value: str, reload = False) -> 'Traitable':
        return cls.s_bclass.load(id_value, reload)

    @classmethod
    def load_many(cls, query: f = None, reload = False) -> list:
        coll = cls.collection()
        cpp_class = cls.s_bclass
        return [ cpp_class.deserialize_object(serialized_data, reload) for serialized_data in coll.find(query) ]

    @classmethod
    def load_ids(cls, query: f = None) -> list:
        coll = cls.collection()
        id_tag = coll.s_id_tag
        return [ serialized_data.get(id_tag) for serialized_data in coll.find(query) ]

    def save(self) -> RC:
        cls = self.__class__
        rc = self.verify()
        if not rc:
            return rc

        rc = self.share(False)  #-- not accepting existing entity values, if any
        if not rc:
            return rc

        serialized_data = self.serialize(True)
        if not serialized_data:     #-- it's a lazy instance - no reason to load and re-save
            return RC_TRUE

        coll = cls.collection()

        try:
            rev = coll.save(serialized_data)
        except Exception as e:
            return RC(False, str(e))

        self._rev = rev
        return RC_TRUE

    def verify(self) -> RC:
        rc = RC_TRUE
        #TODO: implement
        return rc

class traitable_trait(concrete_traits.nucleus_trait, data_type = Traitable, base_class = True):
    def post_ctor(self):
        ...

    def default_value(self):
        def_value = self.default
        if def_value is XNone:
            return def_value

        if isinstance(def_value, str):  #-- id
            return self.data_type.instance_by_id(def_value)

        if isinstance(def_value, dict): #-- trait values
            return self.data_type(**def_value)

        assert False, f'{self.data_type} - may not be constructed from {def_value}'

    def from_str(self, s: str):
        return self.data_type.instance_by_id(s)

    def from_any_xstr(self, value):
        if not isinstance(value, dict):
            return None

        return self.data_type(**value)

class Bundle(Traitable):
    s_bundle_base = None
    s_bundle_members: dict = None

    def __init_subclass__(cls, members_known = False, **kwargs):
        super().__init_subclass__(**kwargs)
        if not cls.s_bundle_base:
            cls.s_bundle_base = cls
            if members_known:
                cls.s_bundle_members = {}
        else:
            assert cls.is_storable(), f'{cls} is not storable'
            base = cls.s_bundle_base
            bundle_members = base.s_bundle_members
            if bundle_members is not None:
                bundle_members[cls.__name__] = cls

            cls.collection_name = base.collection_name
            cls.collection = base.collection

    def serialize(self, embed: bool) -> dict:
        serialized_data = super().serialize(True)
        cls = self.__class__
        if cls.s_bundle_members is None:    #-- members unknown
            serialized_data[Nucleus.CLASS_TAG] = PackageRefactoring.find_class_id(cls)
        else:
            serialized_data[Nucleus.CLASS_TAG] = cls.__name__

        return serialized_data

    @classmethod
    def serialized_class(cls, serialized_data: dict):
        class_id = serialized_data.get(Nucleus.CLASS_TAG)
        if class_id is None:
            raise RuntimeError(f'{cls}: serialized data is missing {Nucleus.CLASS_TAG}\n{serialized_data}')

        if cls.s_bundle_members is None:  #-- members are not known - class_id is a real class_id
            return PackageRefactoring.find_class(class_id)

        #-- class_id is a short class name
        actual_class = cls.s_bundle_members.get(class_id)
        if not actual_class:
            raise RuntimeError(f'{cls}: unknown bundle member {class_id}\n{serialized_data}')

        return actual_class
