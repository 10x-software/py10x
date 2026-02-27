from __future__ import annotations

import functools
import operator
import sys
import warnings
from abc import ABC, abstractmethod
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, get_origin

from py10x_kernel import BTraitable, BTraitableClass, BTraitableProcessor, BTraitFlags, OsUser
from typing_extensions import Self, deprecated

import core_10x.concrete_traits as concrete_traits
from core_10x.environment_variables import EnvVars
from core_10x.global_cache import cache
from core_10x.nucleus import Nucleus

from core_10x.package_refactoring import PackageRefactoring
from core_10x.py_class import PyClass
from core_10x.rc import RC, RC_TRUE
from core_10x.resource import Resource
from core_10x.trait import TRAIT_METHOD, BoundTrait, T, Trait, trait_value
from core_10x.trait_definition import (
    RT,
    M,
    TraitDefinition,
    TraitModification,
    Ui,
)
from core_10x.trait_filter import LE, f
from core_10x.traitable_id import ID
from core_10x.ts_store import TS_STORE, TsStore
from core_10x.sec_keys import SecKeys
from core_10x.xnone import XNone, XNoneType

if TYPE_CHECKING:
    from collections.abc import Generator

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


class StorageHelperDescriptor:
    """Resolves s_storage_helper via __mro__ when in AsOf context; otherwise returns real helper."""

    def __get__(self, obj: Traitable | None, owner: type[Traitable] | None = None) -> AbstractStorableHelper | Self:
        if owner is None:
            return self

        if not (helper := owner.s_storage_helper_cached):
            helper_as_of: StorableHelperAsOf = (
                next(
                    (
                        base_helper
                        for base in owner.__mro__
                        if issubclass(base, Traitable) and isinstance(base_helper := base.s_storage_helper_cached, StorableHelperAsOf)
                    ),
                    None,
                )
                if owner.s_history_class
                else None
            )
            if helper_as_of:
                helper = StorableHelperAsOf(owner, helper_as_of.as_of_time)
            elif not owner.is_storable():
                helper = NotStorableHelper(owner)
            else:
                helper = StorableHelperWithHistory(owner) if owner.s_history_class else StorableHelper(owner)

            owner.s_storage_helper_cached = helper

        return helper


class TraitableMetaclass(type(BTraitable)):
    def __new__(cls, name, bases, class_dict, **kwargs):
        if '__init__' in class_dict and name != 'Traitable':
            raise TypeError(f'Overriding __init__ is not allowed in {name}. Use __post_init__ instead.')
        return super().__new__(cls, name, bases, class_dict | {'__slots__': ()}, **kwargs)


class Traitable(BTraitable, Nucleus, metaclass=TraitableMetaclass):
    s_dir = {}
    s_default_trait_factory = RT
    s_own_trait_definitions = None
    T = UnboundTraitAccessor()

    _collection_name: str = XNone
    _rev: int = XNone

    @classmethod
    @cache
    def rev_trait(cls) -> Trait:
        trait_name = Nucleus.REVISION_TAG()
        return Trait.create(
            trait_name,
            T(0, T.RESERVED, data_type=int),
        )

    @classmethod
    @cache
    def collection_name_trait(cls) -> Trait:
        return Trait.create(
            COLL_NAME_TAG,
            T(T.RESERVED | T.RUNTIME, data_type=str),
        )

    def _collection_name_get(self) -> str:
        return self.id().collection_name or XNone

    def _collection_name_set(self, trait, value) -> RC:
        self.id().collection_name = value
        return RC_TRUE

    @classmethod
    def own_trait_definitions(cls) -> Generator[tuple[str, TraitDefinition]]:
        class_dict = dict(cls.__dict__)
        own_trait_definitions = class_dict.get('s_own_trait_definitions')
        if own_trait_definitions is not None:
            yield from cls.s_own_trait_definitions.items()
            return

        module_dict = sys.modules[cls.__module__].__dict__ if cls.__module__ else {}
        type_annotations = class_dict.get('__annotations__',{})
        type_annotations |= {k: XNoneType for k, v in class_dict.items() if isinstance(v, TraitModification) and k not in type_annotations}

        rc = RC(True)
        for trait_name, trait_def in class_dict.items():
            if isinstance(trait_def, TraitDefinition) and trait_name not in type_annotations:
                rc <<= f'{trait_name} = T(...), but the trait is missing a data type annotation. Use `Any` if needed.'

        for trait_name, dt in type_annotations.items():
            trait_def = class_dict.get(trait_name, class_dict)
            if trait_def is not class_dict and not isinstance(trait_def, TraitDefinition):
                continue

            old_trait: Trait = cls.s_dir.get(trait_name)
            if not (dt := cls.check_trait_type(trait_name, trait_def, old_trait, dt, class_dict, module_dict, rc)):
                continue

            if trait_def is class_dict:  # -- only annotation, not in class_dict
                trait_def = cls.s_default_trait_factory()

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

        rc.throw(TypeError)

    @classmethod
    def check_trait_type(cls, trait_name, trait_def, old_trait, dt, class_dict, module_dict, rc):
        if not dt and old_trait:
            return old_trait.data_type

        if isinstance(dt, str):
            try:
                dt = eval(dt, module_dict, class_dict)
            except Exception as e:
                rc <<= f'Failed to evaluate type annotation string `{dt}` for `{trait_name}`: {e} in {module_dict["__name__"]}'
                return None
        if dt is Self:
            dt = cls
        if dt is Any:
            dt = XNoneType
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

    @classmethod
    def inherited_trait_dirs(cls) -> Generator[dict[str, Trait]]:
        return (base.s_dir for base in reversed(cls.__bases__) if issubclass(base, Traitable))

    @classmethod
    def build_trait_dir(cls):
        class_dict = dict(cls.__dict__)
        module_dict = sys.modules[cls.__module__].__dict__ if cls.__module__ else {}
        type_annotations = class_dict.get('__annotations__',{})
        trait_dir = cls.s_dir
        reserved_storable_traits = {
            Nucleus.REVISION_TAG(): cls.rev_trait(),
            COLL_NAME_TAG: cls.collection_name_trait(),
        }
        trait_dir |= reserved_storable_traits
        trait_dir |= functools.reduce(operator.or_, cls.inherited_trait_dirs(), {})

        rc = RC(True)
        for trait_name, old_trait in trait_dir.items():
            trait_def = class_dict.get(trait_name, class_dict)
            if trait_def is class_dict and any(func_name in class_dict for func_name in Trait.method_defs(trait_name)):
                if cls.check_trait_type(trait_name, trait_def, old_trait, type_annotations.get(trait_name), class_dict, module_dict, rc):
                    trait_def = old_trait.t_def.copy()
                    trait_dir[trait_name] = Trait.create(trait_name, trait_def)

        for trait_name, trait_def in cls.own_trait_definitions():
            trait_def.name = trait_name
            trait_dir[trait_name] = Trait.create(trait_name, trait_def)

        if not cls.is_storable():
            for trait_name in reserved_storable_traits:
                del trait_dir[trait_name]
        rc.throw(TypeError)

    @classmethod
    def traits(cls, flags_on: int | BTraitFlags = 0, flags_off: int | BTraitFlags = 0) -> Generator[Trait, None, None]:
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

    # @staticmethod
    # def find_storable_class(class_id: str):
    #     traitable_class = PackageRefactoring.find_class(class_id)
    #     if not issubclass(traitable_class, Traitable) or not traitable_class.is_storable():
    #         raise TypeError(f'{traitable_class} is not a storable Traitable')
    #
    #     return traitable_class

    s_bclass: BTraitableClass = None
    s_custom_collection = False
    s_history_class = XNone  # -- will be set in __init__subclass__ for storable traitables unless keep_history = False. affects storage only.
    s_immutable = (
        XNone  # -- will be turned on in __init__subclass__ for storable traitables without history unless immutable=False. affects storage only.
    )
    s_direct_subclasses: list[type[Traitable]] = []
    s_storage_helper: AbstractStorableHelper = StorageHelperDescriptor()
    s_storage_helper_cached: AbstractStorableHelper | None = None

    def __init_subclass__(cls, custom_collection: bool = None, keep_history: bool = None, immutable: bool = None, **kwargs):
        if custom_collection is not None:
            cls.s_custom_collection = custom_collection

        cls.s_direct_subclasses = []
        for base in cls.__bases__:
            if issubclass(base, Traitable):
                base.s_direct_subclasses.append(cls)

        cls.s_dir = {}
        cls.s_bclass = BTraitableClass(cls)

        cls.build_trait_dir()  # -- build cls.s_dir from trait definitions in cls.__dict__

        if cls.is_storable():
            if keep_history is False:
                cls.s_history_class = None
            if cls.s_history_class is not None:
                cls.s_history_class = TraitableHistory.history_class(cls)

            cls.s_immutable = cls.s_history_class is None if immutable is None else immutable
        else:
            cls.s_history_class = XNone

        rc = RC(True)
        for trait_name, trait in cls.s_dir.items():
            trait.set_trait_funcs(cls, rc)
            trait.check_integrity(cls, rc)
            setattr(cls, trait_name, trait)
        cls.check_integrity(rc)
        rc.throw()

    @classmethod
    def check_integrity(cls, rc: RC):
        if cls.is_storable() and (rt_id_trait := next((trait for trait in cls.traits(flags_on=T.ID) if trait.flags_on((T.RUNTIME))), None)):
            rc.add_error(f'{cls}.{rt_id_trait.name} is a RUNTIME ID trait - traitable must not be storable (all traits must be RUNTIME)')

    def __init__(self, _id: ID = None, _collection_name: str = None, _skip_init=False, _replace=False, **trait_values):
        cls = self.__class__

        if _id is not None:
            assert _collection_name is None, f'{self.__class__}(id_value) may not be invoked with _collection_name'
            assert not trait_values, f'{self.__class__}(id_value) may not be invoked with trait_values'
            super().__init__(cls.s_bclass, _id)
        else:
            super().__init__(cls.s_bclass, ID(collection_name=_collection_name))
            if not _skip_init:
                self.initialize(trait_values, _replace=_replace)

        self.__post_init__()

    def __post_init__(self):
        # Default no-op; users can override this in subclasses
        pass

    @classmethod
    def existing_instance(cls, _collection_name: str = None, _throw: bool = True, **trait_values) -> Traitable | None:
        if not cls.is_storable() and cls.is_id_endogenous():  # runtime endogenous instances are created on the fly
            return cls(_collection_name=_collection_name, **trait_values)

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

    #-- TODO: should probably have a better performance
    @classmethod
    def existing_instances_by_filter(cls, query: f, _coll_name: str = None, _at_most = 0, _order: dict = None) -> list[Traitable]:
        ids = cls.load_ids(query = query, _coll_name = _coll_name, _at_most = _at_most, _order = _order)
        return [ obj for id in ids if(obj := cls.existing_instance_by_id(_id = id, _collection_name = _coll_name, _throw = False)) ]

    @classmethod
    @deprecated('Use create_or_replace instead.')
    def update(cls, **kwargs) -> Traitable:
        return cls(**kwargs, _replace=True)

    @classmethod
    def new_or_replace(cls, **kwargs) -> Traitable:
        return cls(**kwargs, _replace=True)

    def set_values(self, _ignore_unknown_traits=True, **trait_values) -> RC:
        return self._set_values(trait_values, _ignore_unknown_traits)

    def __getitem__(self, item):
        return self.get_value(item)

    def __setitem__(self, key, value):
        return self.set_value(key, value)

    #===================================================================================================================
    #   The following methods are available from c++
    #
    #   get_value(trait-or-name, *args) -> Any
    #   set_value(trait-or_name, value: Any, *args) -> RC
    #   raw_value(trait-or_name, value: Any, *args) -> RC
    #   invalidate_value(trait-or-name)
    #   verify_trait(trait) -> RC               #-- semantically equiv to verify_trait_value(trait. get_value(trait))
    #   verify_trait_value(trait, value) -> RC
    #   verify()                                #-- verifies each trait and calls post_verify()
    #===================================================================================================================

    #===================================================================================================================
    #   Nucleus related methods
    #===================================================================================================================

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

    #===================================================================================================================
    #   Storage related methods
    #===================================================================================================================

    @classmethod
    def store(cls) -> TsStore:
        store: TsStore = TS_STORE.current_resource()    #-- if current TsStore is set, use it!
        if not store:
            store = cls.store_per_class()               #-- otherwise, use per class store, if any

        if not store:
            raise OSError(f'{cls} - no Traitable Store is available')

        return store

    @staticmethod
    @cache
    def vault_store() -> TsStore:
        uri = SecKeys.check_vault_uri()
        spec = TsStore.spec_from_uri(uri)
        store_class: type[TsStore] = spec.resource_class
        is_running, with_auth = store_class.is_running_with_auth(spec.hostname())
        if not is_running:
            raise OSError(f"Vault Store '{uri}' is not running")

        if with_auth:
            pwd = SecKeys.retrieve_vault_password(vault_uri = uri)
            spec.set_credentials(pwd)

        return store_class.instance(**spec.kwargs)

    @staticmethod
    def store_from_uri(uri: str) -> TsStore:
        spec = TsStore.spec_from_uri(uri)
        store_class: type[ TsStore ] = spec.resource_class
        is_running, with_auth = store_class.is_running_with_auth(spec.hostname())
        if not is_running:
            raise OSError(f"TsStore '{uri}' is not running")

        if with_auth:
            with Traitable.vault_store():
                ra = VaultResourceAccessor.retrieve_ra(uri)
                return ra.resource

        return store_class.instance(**spec.kwargs)

    @staticmethod
    @cache
    def main_store() -> TsStore:
        v_store_uri = EnvVars.var.main_ts_store_uri
        if not v_store_uri:
            raise OSError(f'No Traitable Store is specified: neither explicitly, nor via environment variable {EnvVars.var_name(v_store_uri)}')

        return Traitable.store_from_uri(v_store_uri.value)

    @classmethod
    @cache
    def store_per_class(cls) -> TsStore:
        store = Traitable.main_store()
        #-- check if there's a specific store association with this cls
        if EnvVars.use_ts_store_per_class:
            with store:
                ts_uri = TsClassAssociation.ts_uri(cls)

            if ts_uri:
                store = Traitable.store_from_uri(ts_uri)

        return store

    @classmethod
    def collection(cls, _coll_name: str = None) -> TsCollection | None:
        return cls.s_storage_helper.collection(_coll_name)

    @classmethod
    def exists_in_store(cls, id: ID) -> bool:
        return cls.s_storage_helper.exists_in_store(id)

    @classmethod
    def load_data(cls, id: ID) -> dict | None:
        return cls.s_storage_helper.load_data(id)

    @classmethod
    def delete_in_store(cls, id: ID) -> RC:
        return cls.s_storage_helper.delete_in_store(id)

    @classmethod
    def load(cls, id: ID) -> Traitable | None:
        return cls.s_storage_helper.load(id)

    @classmethod
    def load_many(cls, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None, _deserialize=True) -> list[Self]:
        return cls.s_storage_helper.load_many(query, _coll_name, _at_most, _order, _deserialize)

    @classmethod
    def load_ids(cls, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None) -> list[ID]:
        return cls.s_storage_helper.load_ids(query, _coll_name, _at_most, _order)

    @classmethod
    def delete_collection(cls, _coll_name: str = None) -> bool:
        return cls.s_storage_helper.delete_collection(_coll_name)

    def save(self, save_references=False) -> RC:
        return self.__class__.s_storage_helper.save(self, save_references=save_references)

    def delete(self) -> RC:
        return self.__class__.s_storage_helper.delete(self)

    def post_verify(self) -> RC:
        return RC_TRUE

    @classmethod
    def as_of(cls, traitable_id: ID, as_of_time: datetime) -> Self:
        return cls.s_storage_helper.as_of(traitable_id,as_of_time)

    @classmethod
    def history(cls, _at_most: int = 0, _filter: f = None, _deserialize=False, _collection_name: str = None, _before: datetime = None, **named_filters) -> list:
        """Get history entries for this traitable class."""
        return cls.s_storage_helper.history(_at_most,_filter,_deserialize,_collection_name,_before,**named_filters)

    @classmethod
    def latest_revision(cls, traitable_id: ID, timestamp: datetime = None, deserialize: bool = False) -> dict | TraitableHistory | None:
        """Get the latest revision of a traitable from history."""
        return cls.s_storage_helper.latest_revision(traitable_id,timestamp,deserialize)

    @classmethod
    def restore(cls, traitable_id, timestamp: datetime = None, save=False) -> bool:
        """Restore a traitable to a specific point in time."""
        return cls.s_storage_helper.restore(traitable_id,timestamp,save)

Traitable.s_bclass = BTraitableClass(Traitable)

@dataclass
class AbstractStorableHelper(ABC):
    traitable_class: type[Traitable]

    @abstractmethod
    def collection(self, _coll_name: str = None) -> TsCollection | None: ...

    @abstractmethod
    def exists_in_store(self, id: ID) -> bool: ...

    @abstractmethod
    def load_data(self, id: ID) -> dict | None: ...

    @abstractmethod
    def delete_in_store(self, id: ID) -> RC: ...

    @abstractmethod
    def load(self, id: ID) -> Traitable | None: ...

    @abstractmethod
    def load_many(self, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None, _deserialize=True) -> list[Traitable]: ...

    @abstractmethod
    def load_ids(self, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None) -> list[ID]: ...

    @abstractmethod
    def delete_collection(self, _coll_name: str = None) -> bool: ...

    @abstractmethod
    def save(self, traitable: Traitable, save_references: bool) -> RC: ...

    @abstractmethod
    def _save_serialized(self, coll, serialized_data, old_rev): ...

    @abstractmethod
    def delete(self, traitable: Traitable) -> RC: ...

    @abstractmethod
    def as_of(self, traitable_id: ID, as_of_time: datetime) -> Traitable: ...

    @abstractmethod
    def history(self, _at_most: int = 0, _filter: f = None, _deserialize=False, _collection_name: str = None, _before: datetime = None, **named_filters) -> list: ...

    @abstractmethod
    def latest_revision(self, traitable_id: ID, timestamp: datetime = None, deserialize: bool = False) -> dict | TraitableHistory | None: ...

    @abstractmethod
    def restore(self, traitable_id, timestamp: datetime = None, save=False) -> bool: ...


class NotStorableHelper(AbstractStorableHelper):
    def collection(self, _coll_name: str = None) -> TsCollection | None:
        return None

    def exists_in_store(self, id: ID) -> bool:
        return False

    def load_data(self, id: ID) -> dict | None:
        return None

    def delete_in_store(self, id: ID) -> RC:
        return RC(False, f'{self.traitable_class} is not storable')

    def load(self, id: ID) -> Traitable | None:
        return None

    def load_many(self, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None, _deserialize=True) -> list[Traitable]:
        return []

    def load_ids(self, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None) -> list[ID]:
        return []

    def delete_collection(self, _coll_name: str = None) -> bool:
        return False

    def save(self, traitable: Traitable, save_references: bool) -> RC:
        return RC(False, f'{self.traitable_class} is not storable')

    def _save_serialized(self, coll, serialized_data, old_rev):
        return old_rev

    def delete(self, traitable: Traitable) -> RC:
        return RC(False, f'{self.traitable_class} is not storable')

    def as_of(self, traitable_id: ID, as_of_time: datetime) -> Traitable:
        raise RuntimeError(f'{self.traitable_class} is not storable')

    def history(self, _at_most: int = 0, _filter: f = None, _deserialize=False, _collection_name: str = None, _before: datetime = None, **named_filters) -> list:
        raise RuntimeError(f'{self.traitable_class} is not storable')

    def latest_revision(self, traitable_id: ID, timestamp: datetime = None, deserialize: bool = False) -> dict | TraitableHistory | None:
        raise RuntimeError(f'{self.traitable_class} is not storable')

    def restore(self, traitable_id, timestamp: datetime = None, save=False) -> bool:
        raise RuntimeError(f'{self.traitable_class} is not storable')



class StorableHelper(AbstractStorableHelper):
    def collection(self, _coll_name: str = None) -> TsCollection:
        cls = self.traitable_class
        cname = _coll_name or PackageRefactoring.find_class_id(cls)
        return cls.store().collection(cname)

    def exists_in_store(self, id: ID) -> bool:
        return self.traitable_class.collection(_coll_name=id.collection_name).id_exists(id.value)

    def load_data(self, id: ID) -> dict | None:
        return self.traitable_class.collection(_coll_name=id.collection_name).load(id.value)

    def delete_in_store(self, id: ID) -> RC:
        cls = self.traitable_class
        coll = cls.collection(_coll_name=id.collection_name)
        if not coll:
            return RC(False, f'{cls} - no store available')
        if not coll.delete(id.value):
            return RC(False, f'{cls} - failed to delete {id.value} from {coll}')
        return RC_TRUE

    def load(self, id: ID) -> Traitable | None:
        return self.traitable_class.s_bclass.load(id)

    def _find(self, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None):
        # TODO FUTURE - current state as history query?
        cls = self.traitable_class
        coll = cls.collection(_coll_name=_coll_name)
        return coll.find(f(query, cls.s_bclass), _at_most=_at_most, _order=_order)

    def load_many(
        self, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None, _deserialize: bool = True
    ) -> list[Traitable] | list[dict]:
        cursor = self._find(query=query, _coll_name=_coll_name, _at_most=_at_most, _order=_order)

        if not _deserialize:
            return list(cursor)

        f_deserialize = functools.partial(Traitable.deserialize_object, self.traitable_class.s_bclass, _coll_name)
        return [f_deserialize(serialized_data) for serialized_data in cursor]

    def load_ids(self, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None) -> list[ID]:
        id_tag = self.traitable_class.collection(_coll_name=_coll_name).s_id_tag  # better?
        cursor = self._find(query=query, _coll_name=_coll_name, _at_most=_at_most, _order=_order)
        return [ID(serialized_data.get(id_tag), _coll_name) for serialized_data in cursor]

    def delete_collection(self, _coll_name: str = None) -> bool:
        cls = self.traitable_class
        store = cls.store()
        if not store:
            return False
        cname = _coll_name or PackageRefactoring.find_class_id(cls)
        return store.delete_collection(collection_name=cname)

    def save(self, traitable: Traitable, save_references: bool) -> RC:
        rc = traitable.verify()
        if not rc:
            return rc

        rc = traitable.share(False)  # -- not accepting existing traitable values, if any
        if not rc:
            return rc


        try:
            serialized_data = traitable.serialize_object(save_references)

            if not serialized_data:  # -- it's a lazy instance - no reason to load and re-save
                return RC_TRUE

            coll = self.traitable_class.collection(traitable.id().collection_name)
            if not coll:
                return RC(False, f'{self.__class__} - no store available')

            with self._transaction_ctx():
                rev = self._save_serialized(coll, serialized_data, traitable.get_revision())
        except Exception as e:
            return RC(False, f'Error saving traitable: {e}')

        traitable.set_revision(rev)
        return RC_TRUE

    def _transaction_ctx(self):
        return nullcontext()

    def _save_serialized(self, coll, serialized_data, old_rev) -> int:
        return coll.save_new(serialized_data) if self.traitable_class.s_immutable else coll.save(serialized_data)

    def delete(self, traitable: Traitable) -> RC:
        rc = self.delete_in_store(traitable.id())
        if rc:
            traitable.set_revision(0)
        return rc

    def as_of(self, traitable_id: ID, as_of_time: datetime) -> Traitable:
        raise RuntimeError(f'{self.traitable_class} does not keep history')

    def history(self, _at_most: int = 0, _filter: f = None, _deserialize=False, _collection_name: str = None, _before: datetime = None, **named_filters) -> list:
        raise RuntimeError(f'{self.traitable_class} does not keep history')

    def latest_revision(self, traitable_id: ID, timestamp: datetime = None, deserialize: bool = False) -> dict | TraitableHistory | None:
        raise RuntimeError(f'{self.traitable_class} does not keep history')

    def restore(self, traitable_id, timestamp: datetime = None, save=False) -> bool:
        raise RuntimeError(f'{self.traitable_class} does not keep history')


class StorableHelperWithHistory(StorableHelper):
    def _transaction_ctx(self):
        return self.traitable_class.store().transaction() if EnvVars.use_ts_store_transactions else nullcontext()

    def _save_serialized(self, coll, serialized_data, old_rev) -> int:
        rev = super()._save_serialized(coll, serialized_data, old_rev)
        if rev > old_rev:
            self.traitable_class.s_history_class(
                serialized_traitable=serialized_data,
                _traitable_rev=rev,
                _collection_name=(coll.collection_name() + '#history') if self.traitable_class.s_custom_collection else XNone,
            ).save().throw()
        return rev

    def as_of(self, traitable_id: ID, as_of_time: datetime) -> Self:
        history_entry = self.traitable_class.latest_revision(traitable_id, as_of_time, deserialize=True)
        return history_entry.traitable if history_entry else None

    def history(
        self, _at_most: int = 0, _filter: f = None, _deserialize=False, _collection_name: str = None, _before: datetime = None, **named_filters
    ) -> list:
        cls = self.traitable_class

        if cls.s_custom_collection and not _collection_name:
            raise RuntimeError(f'{cls} requires custom _collection_name')

        if not cls.s_custom_collection and _collection_name:
            raise RuntimeError(f'{cls} does not support custom _collection_name')

        as_of = {'_at': LE(_before)} if _before else {}
        cursor = cls.s_history_class.load_many(
            f(_filter, **named_filters, **as_of),
            _order=dict(_traitable_id=1, _at=-1, _traitable_rev=-1),
            _at_most=_at_most,
            _deserialize=_deserialize,
            _coll_name=_collection_name + '#history' if _collection_name else None,
        )

        return list(cursor)

    def latest_revision(self, traitable_id: ID, timestamp: datetime = None, deserialize: bool = False) -> dict | TraitableHistory | None:
        """Get the latest revision of a traitable from history."""
        for entry in self.traitable_class.history(
            _filter=f(_traitable_id=traitable_id.value),
            _collection_name=traitable_id.collection_name,
            _at_most=1,
            _deserialize=deserialize,
            _before=timestamp,
        ):
            return entry  # Return the raw history entry dict

        return None

    def restore(self, traitable_id, timestamp: datetime = None, save=False) -> bool:
        """Restore a traitable to a specific point in time."""
        history_entry = self.traitable_class.latest_revision(
            traitable_id,
            timestamp,
            deserialize=True,
        )
        if not history_entry or not history_entry.traitable:
            return False

        if save:
            return bool(
                self.traitable_class.collection(
                    traitable_id.collection_name,
                ).save_new(
                    {'$set': history_entry.serialized_traitable},
                    overwrite=True,
                )
            )
        return True


@dataclass
class StorableHelperAsOf(StorableHelperWithHistory):
    as_of_time: datetime

    def _find(self, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None):
        last_id = None
        for item in self.traitable_class.history(
            _filter=query,
            _before=self.as_of_time,
            _collection_name=_coll_name,
            _deserialize=True,
        ):
            # TODO: optimize by returning one entry per id using a pipeline query
            if last_id != item._traitable_id:
                last_id = item._traitable_id
                yield item.serialized_traitable

    def exists_in_store(self, id: ID) -> bool:
        history_entry = self.traitable_class.latest_revision(id, self.as_of_time, deserialize=True)
        return bool(history_entry)  # TODO: optimize by not downloading the latest revision

    def load_data(self, id: ID) -> dict | None:
        history_entry = self.traitable_class.latest_revision(id, self.as_of_time, deserialize=True)
        return history_entry.serialized_traitable if history_entry else None


def __getattr__(name):
    if name == 'THIS_CLASS':  # -- to use for traits with the same Traitable class type
        warnings.warn('THIS_CLASS is deprecated; use typing.Self instead', DeprecationWarning, stacklevel=2)
        return Self
    raise AttributeError(name)


class TraitableHistory(Traitable, keep_history=False):
    s_traitable_class = None
    s_trait_name_map = dict(_traitable_id='_id', _traitable_rev='_rev')

    # fmt: off
    traitable: Traitable        = RT() // 'original traitable'
    serialized_traitable: dict  = RT()

    _at: datetime               = T() // 'time saved'
    _who: str                   = T() // 'authenticated user, if any'
    _traitable_id: str          = T() // 'original traitable id'
    _traitable_rev: int         = T() // 'original traitable rev'
    # fmt: on

    def _traitable_id_get(self) -> str:
        return self.serialized_traitable['_id']

    def serialize_object(self, save_references: bool = False):
        serialized_data = {**self.serialized_traitable, **super().serialize_object(save_references)}
        return self.store().populate(['_who', '_at'], serialized_data)

    def traitable_get(self):
        return Traitable.deserialize_object(
            self.s_traitable_class.s_bclass,
            self._collection_name.rsplit('#', 1)[0] or None,  # -- strip #history suffix
            self.serialized_traitable,
        )

    def deserialize_traits(self, serialized_data):
        hist_data = {trait.name: serialized_data.pop(trait.name, None) for trait in self.traits(flags_off=T.RUNTIME)}
        self.serialized_traitable = serialized_data | {v: hist_data[k] for k, v in self.s_trait_name_map.items()}
        return super().deserialize_traits(hist_data)

    @classmethod
    def store(cls):
        return cls.s_traitable_class.store()

    @classmethod
    def collection(cls, _coll_name: str = None) -> TsCollection | None:
        collection = cls.s_storage_helper.collection(_coll_name)
        collection.create_index('idx_by_traitable_id_time', [('_traitable_id', 1), ('_at', -1)])
        return collection

    @staticmethod
    @cache
    def history_class(traitable_class: type[Traitable]):
        module_dict = sys.modules[traitable_class.__module__].__dict__
        history_class_name = f'{traitable_class.__name__}#history'
        history_class = type(
            history_class_name,
            (TraitableHistory,),
            dict(
                s_traitable_class=traitable_class,
                s_custom_collection=traitable_class.s_custom_collection,
                __module__=traitable_class.__module__,
            ),
        )
        if traitable_class is module_dict.get(traitable_class.__name__):
            assert history_class_name not in module_dict
            module_dict[history_class_name] = history_class
        return history_class


@dataclass
class AsOfContext:
    """Context manager for time-based traitable loading.

    Applies to the given traitable_classes and all their subclasses (discovered via
    s_direct_subclasses). Default is [Traitable], so all storable Traitable subclasses
    use AsOf resolution. s_storage_helper is resolved dynamically via __mro__ and
    cached; the cache is invalidated on enter/exit for all relevant subclasses.
    """

    as_of_time: datetime
    traitable_classes: list[type[Traitable]] = field(default_factory=lambda: [Traitable])

    _btp: BTraitableProcessor | None = None

    def __post_init__(self):
        invalid_class = next((traitable_class for traitable_class in self.traitable_classes if not traitable_class.s_history_class), None)
        if invalid_class and invalid_class is not Traitable:  # we use Traitable as a special case to cover *all* traitables
            raise ValueError(f'{invalid_class} is not storable or does not keep history')

    def _reset_storage_helpers(self):
        visited: set[type[Traitable]] = set()
        stack = list(self.traitable_classes)
        while stack:
            traitable_class = stack.pop()
            if traitable_class in visited:
                continue
            visited.add(traitable_class)
            traitable_class.s_storage_helper_cached = None
            for sub in traitable_class.s_direct_subclasses:
                stack.append(sub)

    def __enter__(self):
        self._reset_storage_helpers()
        for traitable_class in self.traitable_classes:
            traitable_class.s_storage_helper_cached = StorableHelperAsOf(traitable_class, self.as_of_time)

        btp = BTraitableProcessor.create_root()
        btp.begin_using()
        self._btp = btp
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._btp is not None:
            self._btp.end_using()
            self._btp = None

        self._reset_storage_helpers()

class traitable_trait(concrete_traits.nucleus_trait, data_type=Traitable, base_class=True):
    def post_ctor(self): ...

    def check_integrity(self, cls, rc: RC):
        is_anonymous = issubclass(self.data_type, AnonymousTraitable)
        is_runtime = self.flags_on(T.RUNTIME)
        if self.flags_on(T.EMBEDDED):
            if is_runtime:
                rc.add_error(f'{cls.__name__}.{self.name} - cannot be both RUNTIME adn EMBEDDED')
            if not is_anonymous:
                rc.add_error(f'{cls.__name__}.{self.name} - EMBEDDED traitable must be a subclass of AnonymousTraitable')
        else:
            if is_anonymous and not is_runtime:
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

#=======================================================================================================================
#   Vault related stuff
#=======================================================================================================================

class VaultUser(Traitable):
    user_id: str                    = T(T.ID)   // 'OS login'
    suspended: bool                 = T(False)

    private_key_encrypted: bytes    = T()
    public_key: bytes               = T()

    sec_keys: SecKeys               = RT(T.EVAL_ONCE)

    def user_id_get(self) -> str:
        return self.__class__.myname()

    def sec_keys_get(self) -> SecKeys:
        return SecKeys(self.private_key_encrypted, self.public_key, SecKeys.retrieve_master_password())

    @classmethod
    def is_functional_account(cls, user_id: str) -> bool:
        return user_id.split('-', 1) == EnvVars.functional_account_prefix

    @classmethod
    @cache
    def myname(cls) -> str:
        return OsUser.me.name()

    @classmethod
    @cache
    def me(cls) -> VaultUser:
        return cls.existing_instance(user_id=cls.myname())


class VaultResourceAccessor(Traitable):
    username: str           = T(T.ID)
    resource_uri: str       = T(T.ID)

    login: str              = T()
    password: bytes         = T()

    last_updated: datetime  = T(T.EVAL_ONCE)

    user: VaultUser         = RT(T.EVAL_ONCE)
    resource: Resource      = RT(T.EVAL_ONCE)

    def username_get(self) -> str:
        return VaultUser.myname()

    def last_updated_get(self) -> datetime:
        return datetime.utcnow()

    def user_get(self) -> VaultUser:
        return VaultUser.existing_instance(user_id=self.username)

    def resource_get(self) -> Resource:
        return Resource.instance_from_uri(
            self.resource_uri,
            username=self.username,
            password=self.user.sec_keys.decrypt_text(self.password),
        )

    @classmethod
    def save_ra(cls, resource_uri: str, password: str, login: str = None, username: str = XNone) -> RC:
        if login is None:
            login = username

        ra = cls(username = username, resource_uri = resource_uri)
        user = ra.user
        rc = ra.set_values(
            login       = login,
            password    = user.sec_keys.encrypt_text(password),
        )
        if rc:
            rc = ra.save()

        return rc

    #-- strictly speaking this method isn't necessary as it just returning existing_instance()
    @classmethod
    def retrieve_ra(cls, resource_uri: str, username: str = XNone) -> VaultResourceAccessor:
        return cls.existing_instance(username=username, resource_uri=resource_uri)

class NamedTsStore(Traitable):
    logical_name: str   = T(T.ID)
    uri: str            = T()

class TsClassAssociation(Traitable):
    py_canonical_name: str  = T(T.ID)
    ts_logical_name: str    = T(Ui.choice('Store Name'))

    def ts_logical_name_choices(self, trait) -> tuple:
        return tuple(nts.logical_name for nts in NamedTsStore.load_many())

    @classmethod
    @cache
    def store_per_class(cls) -> TsStore:
        return Traitable.main_store()

    @classmethod
    def ts_uri(cls, traitable_class) -> str:
        #-- 1) Check TsStore association for the class itself, its module and packages
        canonical_name = PyClass.name(traitable_class)
        while True:
            association = cls.existing_instance(py_canonical_name=canonical_name, _throw=False)
            if association:
                named_store = NamedTsStore.existing_instance(logical_name=association.ts_logical_name)
                return named_store.uri

            parts = canonical_name.rsplit('.', maxsplit=1)
            name = parts[0]
            if name == canonical_name:  #-- checked all packages bottom up
                break                   #-- no asscciation for the class. module, packages

            canonical_name = name

        #-- 2) Check TsStore association for the class' parent Traitables
        parent_classes = traitable_class.__mro__
        for pclass in parent_classes[1:]:
            if issubclass(pclass, Traitable):
                canonical_name = PyClass.name(pclass)
                association = cls.existing_instance(py_canonical_name=canonical_name, _throw=False)
                if association:
                    named_store = NamedTsStore.existing_instance(logical_name=association.ts_logical_name)
                    return named_store.uri

        return ''
#=======================================================================================================================
