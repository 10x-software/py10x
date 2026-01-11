from __future__ import annotations

import functools
import operator
import sys
from itertools import chain
from typing import TYPE_CHECKING, Any, Self, get_origin

from core_10x_i import BTraitable, BTraitableClass
from typing_extensions import deprecated

import core_10x.concrete_traits as concrete_traits
from core_10x.global_cache import cache
from core_10x.nucleus import Nucleus
from core_10x.package_manifest import PackageManifest
from core_10x.package_refactoring import PackageRefactoring
from core_10x.rc import RC, RC_TRUE
from core_10x.trait import TRAIT_METHOD, BoundTrait, T, Trait, trait_value  # noqa: F401
from core_10x.trait_definition import (  # noqa: F401
    RT,
    M,
    TraitDefinition,
    TraitModification,
    Ui,
)
from core_10x.trait_filter import f
from core_10x.traitable_id import ID
from core_10x.ts_store import TS_STORE, TsStore
from core_10x.environment_variables import EnvVars
from core_10x.xnone import XNone, XNoneType

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from core_10x.ts_store import TsCollection


class TraitAccessor:
    __slots__ = ('cls', 'obj')

    def __init__(self, obj: Traitable):
        self.cls = obj.__class__
        self.obj = obj

    def __getattr__(self, trait_name: str) -> BoundTrait:
        trait = self.cls.trait(trait_name, throw=True)
        return BoundTrait(self.obj, trait)

    def __call__(self, trait_name: str, throw=True) -> Trait:
        return self.cls.trait(trait_name, throw=True)


class UnboundTraitAccessor:
    __slots__ = ()

    def __get__(self, instance, owner):
        return TraitAccessor(instance)


COLL_NAME_TAG = '_collection_name'


class TraitableMetaclass(type(BTraitable)):
    @staticmethod
    def find_symbols(bases, class_dict, symbol):
        return chain(
            (res for res in (class_dict.get(symbol, class_dict),) if res is not class_dict),
            (res for base in bases if (res := getattr(base, symbol, class_dict)) is not class_dict),
        )

    @staticmethod
    @cache
    def rev_trait() -> Trait:
        trait_name = Nucleus.REVISION_TAG()
        return Trait.create(
            trait_name,
            T(0, T.RESERVED, data_type=int),
        )

    @staticmethod
    @cache
    def collection_name_trait() -> Trait:
        trait_name = COLL_NAME_TAG

        def get(self):
            return self.id().collection_name

        def set(self, t, cname) -> RC:
            self.id().collection_name = cname
            return RC_TRUE

        return Trait.create(
            trait_name,
            T(T.RESERVED | T.RUNTIME, data_type=str, get=get, set=set),
        )

    def __new__(cls, name, bases, class_dict, _mixin=False, **kwargs):
        build_trait_dir = next(cls.find_symbols(bases, class_dict, 'build_trait_dir'))

        trait_dir = {
            Nucleus.REVISION_TAG(): cls.rev_trait(),  # -- insert _rev as the first trait and delete later if not needed
            COLL_NAME_TAG: cls.collection_name_trait(),
        }

        build_trait_dir(bases, class_dict, trait_dir).throw(exc=TypeError)  # -- build trait dir_from trait definitions in class_dict

        class_dict.update(
            s_dir=trait_dir,
            __slots__=(),
        )

        return super().__new__(cls, name, bases, class_dict, **kwargs)


class Traitable(BTraitable, Nucleus, metaclass=TraitableMetaclass):
    s_dir = {}
    s_default_trait_factory = RT
    s_own_trait_definitions = {}
    T = UnboundTraitAccessor()

    @staticmethod
    def own_trait_definitions(bases: tuple, inherited_trait_dir: dict, class_dict: dict, rc: RC) -> Generator[tuple[str, TraitDefinition]]:
        own_trait_definitions = class_dict.get('s_own_trait_definitions')
        if own_trait_definitions:
            yield from own_trait_definitions.items()
            return

        default_trait_factory = next(TraitableMetaclass.find_symbols(bases, class_dict, 's_default_trait_factory'), RT)
        type_annotations = class_dict.get('__annotations__') or {}

        type_annotations |= {k: XNoneType for k, v in class_dict.items() if isinstance(v, TraitModification) and k not in type_annotations}
        module_dict = sys.modules[class_dict['__module__']].__dict__ if '__module__' in class_dict else {}
        check_trait_type = next(TraitableMetaclass.find_symbols(bases, class_dict, 'check_trait_type'))

        for trait_name, trait_def in class_dict.items():
            if isinstance(trait_def, TraitDefinition) and trait_name not in type_annotations:
                rc <<= f'{trait_name} = T(...), but the trait is missing a data type annotation. Use `Any` if needed.'

        for trait_name, dt in type_annotations.items():
            trait_def = class_dict.get(trait_name, class_dict)
            if trait_def is not class_dict and not isinstance(trait_def, TraitDefinition):
                continue

            old_trait: Trait = inherited_trait_dir.get(trait_name)
            if not (dt := check_trait_type(trait_name, trait_def, old_trait, dt, class_dict, module_dict, rc)):
                continue

            if dt is Any:
                dt = XNoneType

            if trait_def is class_dict:  # -- only annotation, not in class_dict
                trait_def = default_trait_factory()

            if isinstance(trait_def, TraitModification):
                if not old_trait:
                    rc <<= f'{trait_name} = M(...), but the trait is not defined previously'
                    continue
                trait_def = trait_def.apply(old_trait.t_def)
                if dt is not XNoneType:  # -- the data type is also being modified
                    trait_def.data_type = dt
            else:
                trait_def.data_type = dt

            yield trait_name, trait_def

    @staticmethod
    def check_trait_type(trait_name, trait_def, old_trait, dt, class_dict, module_dict, rc):
        if not dt and old_trait:
            return old_trait.data_type

        if isinstance(dt, str):
            try:
                dt = eval(dt, class_dict, module_dict)
            except Exception as e:
                rc <<= f'Failed to evaluate type annotation string `{dt}` for `{trait_name}`: {e}'
                return None

        try:
            dt_valid = isinstance(dt, type) or get_origin(dt) is not None
        except TypeError:
            dt_valid = False
        if not dt_valid:
            rc <<= f'Expected type for `{trait_name}`, but found {dt} of type {type(dt)}.'
            return None

        if trait_def is class_dict:  # -- only annotation, not in class_dict
            if old_trait and dt is not old_trait.data_type:
                rc <<= f'Attempt to implicitly redefine type for previously defined trait `{trait_name}`.  Use M() if needed.'
                return None

        return dt

    @staticmethod
    def build_trait_dir(bases, class_dict, trait_dir) -> RC:
        rc = RC(True)
        own_trait_definitions: Callable[[tuple, dict, dict, RC], Generator[tuple[str, TraitDefinition]]] = next(
            TraitableMetaclass.find_symbols(bases, class_dict, 'own_trait_definitions')
        )
        trait_dir |= functools.reduce(operator.or_, TraitableMetaclass.find_symbols(reversed(bases), class_dict, 's_dir'), {})  # -- shallow copy!
        type_annotations = class_dict.get('__annotations__') or {}
        module_dict = sys.modules[class_dict['__module__']].__dict__ if '__module__' in class_dict else {}
        check_trait_type = next(TraitableMetaclass.find_symbols(bases, class_dict, 'check_trait_type'))

        for trait_name, old_trait in trait_dir.items():
            trait_def = class_dict.get(trait_name, class_dict)
            dt = type_annotations.get(trait_name)
            if trait_def is class_dict and any(func_name in class_dict for func_name in Trait.method_defs(trait_name)):
                if check_trait_type(trait_name, trait_def, old_trait, dt, class_dict, module_dict, rc):
                    trait_def = old_trait.t_def.copy()
                    trait_dir[trait_name] = Trait.create(trait_name, trait_def)

        for trait_name, trait_def in own_trait_definitions(bases, trait_dir, class_dict, rc):
            trait_def.name = trait_name
            trait_dir[trait_name] = Trait.create(trait_name, trait_def)

        return rc

    @classmethod
    def traits(cls, flags_on: int = 0, flags_off: int = 0) -> Generator[Trait, None, None]:
        return (t for t in cls.s_dir.values() if (not flags_on or t.flags_on(flags_on)) and not t.flags_on(flags_off))

    def __hash__(self):
        return hash(self.id())

    @classmethod
    def trait(cls, trait_name: str, throw: bool = False) -> Trait:
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
    s_custom_collection = False

    def __init_subclass__(cls, custom_collection: bool = None, **kwargs):
        if custom_collection is not None:
            cls.s_custom_collection = custom_collection

        cls.s_bclass = BTraitableClass(cls)

        if not cls.is_storable():
            del cls.s_dir[Nucleus.REVISION_TAG()]
            del cls.s_dir[COLL_NAME_TAG]
            cls.s_storage_helper = NotStorableHelper()
        else:
            cls.s_storage_helper = StorableHelper()

        rc = RC(True)
        for trait_name, trait in cls.s_dir.items():
            trait.set_trait_funcs(cls, rc)
            if trait.data_type is THIS_CLASS:
                trait.data_type = cls
            trait.check_integrity(cls, rc)
            setattr(cls, trait_name, trait)
        cls.check_integrity(rc)
        rc.throw()

    @classmethod
    def check_integrity(cls, rc: RC):
        pass

    # @classmethod
    # def instance_by_id(cls, id_value: str) -> 'Traitable':
    #     #    return cls.load(id_value)
    #     return cls(_id = id_value)      #-- TODO: we may not need this method, unless used to enforce loading

    def __init__(self, _id: ID = None, _collection_name: str = None, _skip_init=False, _force=False, **trait_values):
        cls = self.__class__

        if _id is not None:
            assert _collection_name is None, f'{self.__class__}(id_value) may not be invoked with _collection_name'
            assert not trait_values, f'{self.__class__}(id_value) may not be invoked with trait_values'
            super().__init__(cls.s_bclass, _id)
        else:
            super().__init__(cls.s_bclass, ID(collection_name=_collection_name))
            if not _skip_init:
                if '_force' in BTraitable.initialize.__doc__:
                    self.initialize(trait_values, _force)
                else:
                    # TODO: compatibility code - remove
                    self.initialize(trait_values)

    @classmethod
    def existing_instance(cls, _collection_name: str = None, _throw: bool = True, **trait_values) -> Traitable | None:
        obj = cls(_collection_name=_collection_name, _skip_init=True)
        if not obj.accept_existing(trait_values):
            if _throw:
                raise ValueError(f'Instance does not exist: {cls}({trait_values})')
            return None

        return obj

    @classmethod
    def existing_instance_by_id(cls, _id: ID = None, _id_value: str = None, _collection_name: str = None, _throw: bool = True) -> Traitable | None:
        if _id is None:
            _id = ID(_id_value, _collection_name)
        obj = cls(_id=_id)
        if obj.id_exists():
            return obj

        if _throw:
            raise ValueError(f'Instance does not exist: {cls}.{_id_value}')

        return None

    @classmethod
    @deprecated('Use constructor with _force=True instead.')
    def update(cls, **kwargs) -> Traitable:
        if '_force' in BTraitable.initialize.__doc__:
            return cls(**kwargs, _force=True)

        # TODO: compatibility code - remove
        o = cls(**{k: v for k, v in kwargs.items() if not (t := cls.s_dir.get(k)) or t.flags_on(T.ID)})
        o.set_values(**{k: v for k, v in kwargs.items() if (t := cls.s_dir.get(k)) and not t.flags_on(T.ID)}).throw()
        return o

    def set_values(self, _ignore_unknown_traits=True, **trait_values) -> RC:
        return self._set_values(trait_values, _ignore_unknown_traits)

    def __getitem__(self, item):
        return self.get_value(item)

    def __setitem__(self, key, value):
        return self.set_value(key, value)

    # ===================================================================================================================
    #   The following methods are available from c++
    #
    #   get_value(trait-or-name, *args) -> Any
    #   set_value(trait-or_name, value: Any, *args) -> RC
    #   raw_value(trait-or_name, value: Any, *args) -> RC
    #   invalidate_value(trait-or-name)
    # ===================================================================================================================

    # ===================================================================================================================
    #   Nucleus related methods
    # ===================================================================================================================

    def serialize(self, embed: bool):
        return self.serialize_nx(embed)

    @classmethod
    def is_bundle(cls) -> bool:
        return cls.serialize_class_id is not Traitable.serialize_class_id

    @classmethod
    def serialize_class_id(cls) -> str | None:
        return None

    @classmethod
    def deserialize_class_id(cls, serialized_class_id: str):
        return cls

    @classmethod
    def deserialize(cls, serialized_data) -> Traitable:
        return Traitable.deserialize_nx(cls.s_bclass, serialized_data)

    def to_str(self) -> str:
        return f'{self.id()}'

    @classmethod
    def from_str(cls, s: str) -> Nucleus:
        # return cls(ID(s))  # collection name?
        return cls.existing_instance_by_id(_id_value=s)

    @classmethod
    def from_any_xstr(cls, value) -> Nucleus:
        if isinstance(value, dict):
            return cls(**value)

        raise TypeError(f'{cls}.from_any_xstr() expects a dict, got {value})')

    @classmethod
    def same_values(cls, value1, value2) -> bool:
        if type(value2) is str:
            return value1.id().value == value2

        return value1.id() == value2.id()

    # ===================================================================================================================
    #   Storage related methods
    # ===================================================================================================================

    @staticmethod
    @cache
    def _bound_data_domain(domain):
        from core_10x.backbone.bound_data_domain import BoundDataDomain

        bb_store = BoundDataDomain.store()
        if not bb_store:
            raise OSError('No Store is available: neither current Store is set nor 10X Backbone host is defined')

        bbd = BoundDataDomain(domain=domain)
        bbd.reload()
        return bbd

    @classmethod
    @cache
    def preferred_store(cls) -> TsStore | None:
        rr = PackageManifest.resource_requirements(cls)
        if not rr:
            return None

        bbd = Traitable._bound_data_domain(rr.domain)
        return bbd.resource(rr.category, throw=False) if bbd else None

    @classmethod
    def store(cls) -> TsStore:
        store: TsStore = TS_STORE.current_resource()
        if not store:
            bb_host = EnvVars.backbone_store_host_name
            if not bb_host:
                store_uri = EnvVars.traitable_store_uri
                if not store_uri:
                    raise OSError('No Traitable Store is specified: neither explicitly, nor via backbone or URI')

                store = TsStore.instance_from_uri(store_uri)
                store.begin_using()

            else:
                store = cls.preferred_store()
                if not store:
                    raise OSError(f'{cls} - failed to find a store')

        return store

    @classmethod
    def collection(cls, _coll_name: str = None) -> TsCollection | None:
        return cls.s_storage_helper.collection(cls, _coll_name)

    @classmethod
    def exists_in_store(cls, id: ID) -> bool:
        return cls.s_storage_helper.exists_in_store(cls, id)

    @classmethod
    def load_data(cls, id: ID) -> dict | None:
        return cls.s_storage_helper.load_data(cls, id)

    @classmethod
    def delete_in_store(cls, id: ID) -> RC:
        return cls.s_storage_helper.delete_in_store(cls, id)

    @classmethod
    def load(cls, id: ID) -> Traitable | None:
        return cls.s_storage_helper.load(cls, id)

    @classmethod
    def load_many(cls, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None, _deserialize=True) -> list[Self]:
        return cls.s_storage_helper.load_many(cls, query, _coll_name, _at_most, _order, _deserialize)

    @classmethod
    def load_ids(cls, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None) -> list[ID]:
        return cls.s_storage_helper.load_ids(cls, query, _coll_name, _at_most, _order)

    @classmethod
    def delete_collection(cls, _coll_name: str = None) -> bool:
        return cls.s_storage_helper.delete_collection(cls, _coll_name)

    def save(self, save_references=False) -> RC:
        return self.__class__.s_storage_helper.save(self, save_references=save_references)

    def delete(self) -> RC:
        return self.__class__.s_storage_helper.delete(self)

    def verify(self) -> RC:
        rc = RC_TRUE
        # TODO: implement
        return rc


Traitable.s_bclass = BTraitableClass(Traitable)


class NotStorableHelper:
    @staticmethod
    def collection(cls, _coll_name: str = None) -> TsCollection | None:
        return None

    @staticmethod
    def exists_in_store(cls, id: ID) -> bool:
        return False

    @staticmethod
    def load_data(cls, id: ID) -> dict | None:
        return None

    @staticmethod
    def delete_in_store(cls, id: ID) -> RC:
        return RC(False, f'{cls.__class__} is not storable')

    @staticmethod
    def load(cls, id: ID) -> Traitable | None:
        return None

    @staticmethod
    def load_many(cls, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None, _deserialize=True) -> list[Traitable]:
        return []

    @staticmethod
    def load_ids(cls, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None) -> list[ID]:
        return []

    @staticmethod
    def delete_collection(cls, _coll_name: str = None) -> bool:
        return False

    @staticmethod
    def save(self, save_references) -> RC:
        return RC(False, f'{self.__class__} is not storable')

    @staticmethod
    def delete(self) -> RC:
        return RC(False, f'{self.__class__} is not storable')


class StorableHelper(NotStorableHelper):
    @staticmethod
    def collection(cls, _coll_name: str = None) -> TsCollection:
        cname = _coll_name or PackageRefactoring.find_class_id(cls)
        return cls.store().collection(cname)

    @staticmethod
    def exists_in_store(cls, id: ID) -> bool:
        coll = cls.collection(_coll_name=id.collection_name)
        return coll.id_exists(id.value) if coll else False

    @staticmethod
    def load_data(cls, id: ID) -> dict:
        coll = cls.collection(_coll_name=id.collection_name)
        return coll.load(id.value) if coll else None

    @staticmethod
    def delete_in_store(cls, id: ID) -> RC:
        coll = cls.collection(_coll_name=id.collection_name)
        if not coll:
            return RC(False, f'{cls} - no store available')
        if not coll.delete(id.value):
            return RC(False, f'{cls} - failed to delete {id.value} from {coll}')
        return RC_TRUE

    @staticmethod
    def load(cls, id: ID) -> Traitable:
        return cls.s_bclass.load(id)

    @staticmethod
    def load_many(cls, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None, _deserialize: bool = True) -> list[Traitable]:
        coll = cls.collection(_coll_name=_coll_name)
        cursor = coll.find(f(query, cls.s_bclass), _at_most=_at_most, _order=_order)
        if not _deserialize:
            return list(cursor)
        f_deserialize = functools.partial(Traitable.deserialize_object, cls.s_bclass, _coll_name)
        return [f_deserialize(serialized_data) for serialized_data in cursor]

    @staticmethod
    def load_ids(cls, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None) -> list[ID]:
        coll = cls.collection(_coll_name=_coll_name)
        id_tag = coll.s_id_tag
        cursor = coll.find(query, _at_most=_at_most, _order=_order)
        return [ID(serialized_data.get(id_tag), _coll_name) for serialized_data in cursor]

    @staticmethod
    def delete_collection(cls, _coll_name: str = None) -> bool:
        store = cls.store()
        if not store:
            return False
        cname = _coll_name or PackageRefactoring.find_class_id(cls)
        return store.delete_collection(collection_name=cname)

    @staticmethod
    def save(self, save_references) -> RC:
        cls = self.__class__
        rc = self.verify()
        if not rc:
            return rc

        rc = self.share(False)  # -- not accepting existing entity values, if any
        if not rc:
            return rc

        if 'save_references' in BTraitable.serialize_object.__doc__:
            serialized_data = self.serialize_object(save_references)
        else:
            # TODO: compatibility code - remove
            serialized_data = self.serialize_object()

        if not serialized_data:  # -- it's a lazy instance - no reason to load and re-save
            return RC_TRUE

        coll = cls.collection()
        if not coll:
            return RC(False, f'{cls} - no store available')

        try:
            rev = coll.save(serialized_data)
        except Exception as e:
            return RC(False, str(e))

        self.set_revision(rev)
        return RC_TRUE

    @staticmethod
    def delete(self) -> RC:
        rc = self.delete_in_store(self.id())
        if rc:
            self.set_revision(0)
        return rc


class THIS_CLASS(Traitable): ...  # -- to use for traits with the same Traitable class type


class traitable_trait(concrete_traits.nucleus_trait, data_type=Traitable, base_class=True):
    def post_ctor(self): ...

    def check_integrity(self, cls, rc: RC):
        is_anonymous = issubclass(self.data_type, AnonymousTraitable)
        if self.flags_on(T.EMBEDDED):
            if not is_anonymous:
                rc.add_error(f'{cls.__name__}.{self.name} - EMBEDDED traitable must be a subclass of AnonymousTraitable')
        else:
            if is_anonymous:
                rc.add_error(f'{cls.__name__}.{self.name} - may not have a reference to AnonymousTraitable (the trait must be T.EMBEDDED)')

    def default_value(self):
        def_value = self.default
        if def_value is XNone:
            return def_value

        if isinstance(def_value, str):  # -- id
            return self.data_type.instance_by_id(def_value)

        if isinstance(def_value, dict):  # -- trait values
            return self.data_type(**def_value)

        raise ValueError(f'{self.data_type} - may not be constructed from {def_value}')

    def from_str(self, s: str):
        return self.data_type.from_str(s)

    def from_any_xstr(self, value):
        if not isinstance(value, dict):
            return None

        return self.data_type(**value)


class Bundle(Traitable):
    s_bundle_base = None
    s_bundle_members: dict = None

    def __init_subclass__(cls, members_known=False, **kwargs):
        super().__init_subclass__(**kwargs)
        if not cls.s_bundle_base:
            cls.s_bundle_base = cls
            if members_known:
                cls.s_bundle_members = {}
        else:
            assert cls.is_storable(), f'{cls} is not storable'
            base = cls.s_bundle_base
            if base:
                bundle_members = base.s_bundle_members
                if bundle_members is not None:
                    bundle_members[cls.__name__] = cls

                # cls.collection_name = base.collection_name #TODO: fix
                cls.collection = base.collection
            assert cls.s_bundle_base, 'bundle base not defined'

    @classmethod
    def serialize_class_id(cls) -> str:
        if cls.s_bundle_members is None:  # -- members unknown
            return PackageRefactoring.find_class_id(cls)
        else:
            return cls.__name__

    @classmethod
    def deserialize_class_id(cls, serialized_class_id: str):
        if not serialized_class_id:
            raise ValueError('missing serialized class ID')

        if cls.s_bundle_members is None:  # -- members are not known - class_id is a real class_id
            return PackageRefactoring.find_class(serialized_class_id)

        # -- class_id is a short class name
        actual_class = cls.s_bundle_members.get(serialized_class_id)
        if not actual_class:
            raise ValueError(f'{cls}: unknown bundle member {serialized_class_id}')

        return actual_class


class AnonymousTraitable(Traitable):
    _me = True

    @classmethod
    def check_integrity(cls, rc: RC):
        if cls._me:
            cls._me = False
            return

        if cls is not AnonymousTraitable:
            if not cls.is_storable():
                rc.add_error(f'{cls} - anonymous traitable must be storable')

            if cls.is_id_endogenous():
                rc.add_error(f'{cls} - anonymous traitable may not have ID traits')

    @classmethod
    def collection(cls, _coll_name: str = None):
        raise AssertionError('AnonymousTraitable may not have a collection')
