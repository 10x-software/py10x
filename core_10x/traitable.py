from __future__ import annotations

import functools
import operator
import sys
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from itertools import chain
from typing import TYPE_CHECKING, Any, Self, get_origin

from core_10x_i import BTraitable, BTraitableClass

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
from core_10x.ts_store import TS_STORE
from core_10x.xnone import XNone, XNoneType

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from core_10x.ts_store import TsCollection, TsStore


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
        # noinspection PyTypeChecker
        t_def: TraitDefinition = T(0, T.RESERVED)
        return Trait.create(trait_name, t_def, {}, {trait_name: int}, RC_TRUE)

    @staticmethod
    @cache
    def collection_name_trait() -> Trait:
        trait_name = COLL_NAME_TAG
        # noinspection PyTypeChecker
        t_def: TraitDefinition = T(T.RESERVED | T.RUNTIME)

        def get(self):
            return self.id().collection_name

        def set(self, t, cname) -> RC:
            self.id().collection_name = cname
            return RC_TRUE

        return Trait.create(
            trait_name,
            t_def,
            {
                f'{trait_name}_get': get,
                f'{trait_name}_set': set,
            },
            {trait_name: str},
            RC_TRUE,
        )

    def __new__(cls, name, bases, class_dict, **kwargs):
        build_trait_dir = next(cls.find_symbols(bases, class_dict, 'build_trait_dir'))
        special_attributes = tuple(chain.from_iterable(cls.find_symbols(bases, class_dict, 's_special_attributes')))

        trait_dir = {
            Nucleus.REVISION_TAG(): cls.rev_trait(),  # -- insert _rev as the first trait and delete later if not needed
            COLL_NAME_TAG: cls.collection_name_trait(),
        }

        build_trait_dir(bases, class_dict, trait_dir).throw(exc=TypeError)  # -- build trait dir_from trait definitions in class_dict

        for item in trait_dir:
            if item in class_dict:
                del class_dict[item]  # -- delete trait names from class_dict as they will be in __slots__

        class_dict.update(
            s_dir=trait_dir,
            __slots__=(*special_attributes, *tuple(trait_dir.keys())),
            s_special_attributes=special_attributes,
        )

        return super().__new__(cls, name, bases, class_dict, **kwargs)


class Traitable(BTraitable, Nucleus, metaclass=TraitableMetaclass):
    s_dir = {}
    s_default_trait_factory = RT
    s_own_trait_definitions = {}

    @staticmethod
    def own_trait_definitions(bases: tuple, inherited_trait_dir: dict, class_dict: dict, rc: RC) -> Generator[tuple[str, TraitDefinition]]:
        own_trait_definitions = class_dict.get('s_own_trait_definitions')
        if own_trait_definitions:
            yield from own_trait_definitions.items()
            return

        default_trait_factory = next(TraitableMetaclass.find_symbols(bases, class_dict, 's_default_trait_factory'), RT)
        annotations = class_dict.get('__annotations__') or {}

        annotations |= {k: XNoneType for k, v in class_dict.items() if isinstance(v, TraitModification) and k not in annotations}
        module_dict = sys.modules[class_dict['__module__']].__dict__ if '__module__' in class_dict else {}
        for trait_name, trait_def in class_dict.items():
            if isinstance(trait_def, TraitDefinition) and trait_name not in annotations:
                rc <<= f'{trait_name} = T(...), but the trait is missing a data type annotation. Use `Any` if needed.'

        for trait_name, dt in annotations.items():
            trait_def = class_dict.get(trait_name, class_dict)
            if trait_def is not class_dict and not isinstance(trait_def, TraitDefinition):
                continue

            if isinstance(dt, str):
                try:
                    dt = eval(dt, class_dict, module_dict)
                except Exception as e:
                    rc <<= f'Failed to evaluate type annotation string `{dt}` for `{trait_name}`: {e}'
                    continue

            try:
                dt_valid = isinstance(dt, type) or get_origin(dt) is not None
            except TypeError:
                dt_valid = False
            if not dt_valid:
                rc <<= f'Expected type for `{trait_name}`, but found {dt} of type {type(dt)}.'
                continue

            old_trait: Trait = inherited_trait_dir.get(trait_name)
            if trait_def is class_dict:  # -- only annotation, not in class_dict
                if old_trait and dt is not old_trait.data_type:
                    rc <<= f'Attempt to implicitly redefine type for previously defined trait `{trait_name}`.  Use M() if needed.'
                    continue
                trait_def = default_trait_factory()

            dt = XNoneType if not dt or dt is Any else dt
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
    def build_trait_dir(bases, class_dict, trait_dir) -> RC:
        rc = RC(True)
        own_trait_definitions: Callable[[tuple, dict, dict, RC], Generator[tuple[str, TraitDefinition]]] = next(
            TraitableMetaclass.find_symbols(bases, class_dict, 'own_trait_definitions')
        )
        trait_dir |= functools.reduce(operator.or_, TraitableMetaclass.find_symbols(bases, class_dict, 's_dir'), {})  # -- shallow copy!
        annotations = class_dict.get('__annotations__') or {}

        for trait_name, old_trait in trait_dir.items():
            if any(func_name in class_dict for func_name in Trait.method_defs(trait_name)):
                t_def = old_trait.t_def
                trait_dir[trait_name] = Trait.create(trait_name, t_def, class_dict, {trait_name: t_def.data_type} | annotations, rc)

        for trait_name, trait_def in own_trait_definitions(bases, trait_dir, class_dict, rc):
            trait_def.name = trait_name
            trait_dir[trait_name] = Trait.create(trait_name, trait_def, class_dict, {}, rc)

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
    s_special_attributes = (
        'T',
        '_default_cache',
    )
    s_custom_collection = False
    s_keep_history = True

    def __init_subclass__(cls, custom_collection: bool = None, keep_history: bool = None, **kwargs):
        if custom_collection is not None:
            cls.s_custom_collection = custom_collection

        if keep_history is not None:
            cls.s_keep_history = keep_history

        cls.s_bclass = BTraitableClass(cls)

        if not cls.is_storable():
            del cls.s_dir[Nucleus.REVISION_TAG()]
            del cls.s_dir[COLL_NAME_TAG]
            cls.s_storage_helper = NotStorableHelper(cls)
        else:
            cls.s_storage_helper = StorableHelper(cls)

        rc = RC(True)
        for trait_name, trait in cls.s_dir.items():
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

    def __init__(self, _id: ID = None, _collection_name: str = None, _skip_init=False, **trait_values):
        cls = self.__class__
        if _id is not None:
            assert _collection_name is None, f'{self.__class__}(id_value) may not be invoked with _collection_name'
            assert not trait_values, f'{self.__class__}(id_value) may not be invoked with trait_values'
            super().__init__(cls.s_bclass, _id)
        else:
            super().__init__(cls.s_bclass, ID(collection_name=_collection_name))
            if not _skip_init:
                self.initialize(trait_values)

        self.T = TraitAccessor(self)

    @classmethod
    def existing_instance(cls, _collection_name: str = None, **trait_values) -> Traitable:
        obj = cls(_collection_name=_collection_name, _skip_init=True)
        if not obj.object_exists(trait_values):
            return None

        return obj

    @classmethod
    def existing_instance_by_id(cls, _id: ID = None, _id_value: str = None, _collection_name: str = None) -> Traitable:
        if _id is None:
            _id = ID(_id_value, _collection_name)
        obj = cls(_id=_id)
        return obj if obj.id_exists() else None

    @classmethod
    def update(cls, **kwargs) -> Traitable:
        o = cls(**{k: v for k, v in kwargs.items() if not (t := cls.s_dir.get(k)) or t.flags_on(T.ID)})
        o.set_values(**{k: v for k, v in kwargs.items() if (t := cls.s_dir.get(k)) and not t.flags_on(T.ID)}).throw()
        return o

    def set_values(self, _ignore_unknown_traits=True, **trait_values) -> RC:
        return self._set_values(trait_values, _ignore_unknown_traits)

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
        return cls(ID(s))  # collection name?

    @classmethod
    def from_any_xstr(cls, value) -> Nucleus:
        if isinstance(value, dict):
            return cls(**value)

        raise TypeError(f'{cls}.from_any_xstr() expects a dict, got {value})')

    @classmethod
    def same_values(cls, value1, value2) -> bool:
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
            store = cls.preferred_store()
            if not store:
                raise OSError(f'{cls} - failed to find a store')

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
    def load(cls, id: ID, as_of: datetime = None) -> Traitable | None:
        return cls.s_storage_helper.load(id, as_of)

    @classmethod
    def load_many(
        cls, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None, _deserialize=True, as_of: datetime = None
    ) -> list[Self]:
        return cls.s_storage_helper.load_many(query, _coll_name, _at_most, _order, _deserialize, as_of)

    @classmethod
    def load_ids(cls, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None, as_of: datetime = None) -> list[ID]:
        return cls.s_storage_helper.load_ids(query, _coll_name, _at_most, _order, as_of)

    @classmethod
    def delete_collection(cls, _coll_name: str = None) -> bool:
        return cls.s_storage_helper.delete_collection(_coll_name)

    def save(self) -> RC:
        return self.__class__.s_storage_helper.save(self)

    def delete(self) -> RC:
        return self.__class__.s_storage_helper.delete(self)

    def verify(self) -> RC:
        rc = RC_TRUE
        # TODO: implement
        return rc

    @classmethod
    def as_of(cls, as_of_time: datetime) -> AsOfContext:
        """Create an asOf context for time-based entity loading."""
        return AsOfContext(cls, as_of_time)

    @classmethod
    def history(cls, _at_most: int = -1, _filter: f = None, **named_filters) -> list:
        """Get history entries for this traitable class."""
        return TraitableHistory.history(cls, _at_most, _filter, **named_filters)

    @classmethod
    def latest_revision(cls, entity_id) -> dict:
        """Get the latest revision of an entity from history."""
        return TraitableHistory.latest_revision(cls, entity_id)

    @classmethod
    def restore(cls, entity_id, timestamp: datetime = None) -> bool:
        """Restore an entity to a specific point in time."""
        return TraitableHistory.restore(cls, entity_id, timestamp)


@dataclass
class AbstractStorableHelper(ABC):
    traitable_class: type[Traitable]
    as_of_time: datetime = None

    @abstractmethod
    def collection(self, _coll_name: str = None) -> TsCollection | None: ...

    @abstractmethod
    def history_collection(self, _coll_name: str = None) -> TsCollection | None: ...

    @abstractmethod
    def exists_in_store(self, id: ID) -> bool: ...

    @abstractmethod
    def load_data(self, id: ID) -> dict | None: ...

    @abstractmethod
    def delete_in_store(self, id: ID) -> RC: ...

    @abstractmethod
    def load(self, id: ID, as_of: datetime = None) -> Traitable | None: ...

    @abstractmethod
    def load_many(
        self, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None, _deserialize=True, as_of: datetime = None
    ) -> list[Traitable]: ...

    @abstractmethod
    def load_ids(self, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None, as_of: datetime = None) -> list[ID]: ...

    @abstractmethod
    def delete_collection(self, _coll_name: str = None) -> bool: ...

    @abstractmethod
    def save(self, traitable_instance) -> RC: ...

    @abstractmethod
    def delete(self, traitable_instance) -> RC: ...


class NotStorableHelper(AbstractStorableHelper):
    def collection(self, _coll_name: str = None) -> TsCollection | None:
        return None

    def history_collection(self, _coll_name: str = None) -> TsCollection | None:
        return None

    def exists_in_store(self, id: ID) -> bool:
        return False

    def load_data(self, id: ID) -> dict | None:
        return None

    def delete_in_store(self, id: ID) -> RC:
        return RC(False, f'{self.traitable_class} is not storable')

    def load(self, id: ID, as_of: datetime = None) -> Traitable | None:
        return None

    def load_many(
        self, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None, _deserialize=True, as_of: datetime = None
    ) -> list[Traitable]:
        return []

    def load_ids(self, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None, as_of: datetime = None) -> list[ID]:
        return []

    def delete_collection(self, _coll_name: str = None) -> bool:
        return False

    def save(self, traitable_instance) -> RC:
        return RC(False, f'{self.traitable_class} is not storable')

    def delete(self, traitable_instance) -> RC:
        return RC(False, f'{self.traitable_class} is not storable')


class StorableHelper(AbstractStorableHelper):
    def collection(self, _coll_name: str = None) -> TsCollection:
        cls = self.traitable_class
        cname = _coll_name or PackageRefactoring.find_class_id(cls)
        return cls.store().collection(cname)

    def history_collection(self, _coll_name: str = None) -> TsCollection:
        """Get the history collection for a traitable class."""
        cls = self.traitable_class
        history_name = TraitableHistory.collection_name(cls, _coll_name)
        history_coll = cls.store().collection(history_name)

        # Create required indexes if they don't exist
        if history_coll:
            try:
                # Create index on _id and _at for efficient time-based queries
                history_coll.create_index('history_id_time', [cls.s_bclass.s_id_tag, '_at'])
                # Create index on _at for time-based filtering
                history_coll.create_index('history_time', '_at')
            except Exception:
                # Index creation failed, but continue - indexes might already exist
                pass

        return history_coll

    def exists_in_store(self, id: ID) -> bool:
        # TODO: respect as_of
        coll = self.collection(_coll_name=id.collection_name)
        return coll.id_exists(id.value) if coll else False

    def load_data(self, id: ID) -> dict:
        # TODO: respect as_of
        coll = self.collection(_coll_name=id.collection_name)
        return coll.load(id.value) if coll else None

    def delete_in_store(self, id: ID) -> RC:
        cls = self.traitable_class
        coll = self.collection(_coll_name=id.collection_name)
        if not coll:
            return RC(False, f'{cls} - no store available')
        if not coll.delete(id.value):
            return RC(False, f'{cls} - failed to delete {id.value} from {coll}')
        return RC_TRUE

    def load(self, id: ID, as_of: datetime = None) -> Traitable | None:
        # Use instance as_of_time if not provided
        cls = self.traitable_class
        as_of = as_of or self.as_of_time

        if as_of is not None:
            # Load from history collection
            history_coll = self.history_collection(_coll_name=id.collection_name)
            if history_coll:
                # Find the most recent history entry before or at the specified time
                from core_10x.trait_filter import f

                query = f(**{cls.s_bclass.s_id_tag: id.value, '_at': {'$lte': as_of}})
                cursor = history_coll.find(query, _order={'_at': -1}, _at_most=1)
                for history_data in cursor:
                    # Remove the _at field and deserialize
                    history_data_copy = history_data.copy()
                    del history_data_copy['_at']
                    return cls.s_bclass.deserialize_object(history_data_copy, id.collection_name)
            return None
        return cls.s_bclass.load(id)

    def load_many(
        self, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None, _deserialize: bool = True, as_of: datetime = None
    ) -> list[Traitable]:
        # Use instance as_of_time if not provided
        cls = self.traitable_class
        as_of = as_of or self.as_of_time

        if as_of is not None:
            # Load from history collection
            history_coll = self.history_collection(_coll_name=_coll_name)
            if history_coll:
                # Add time filter to query
                from core_10x.trait_filter import f

                time_query = f(**{'_at': {'$lte': as_of}})
                combined_query = f(query, cls.s_bclass) & time_query if query else time_query
                cursor = history_coll.find(combined_query, _at_most=_at_most, _order=_order)
                if not _deserialize:
                    return list(cursor)
                # Remove _at field and deserialize
                result = []
                for history_data in cursor:
                    history_data_copy = history_data.copy()
                    del history_data_copy['_at']
                    result.append(cls.s_bclass.deserialize_object(history_data_copy, _coll_name))
                return result
            return []

        coll = self.collection(_coll_name=_coll_name)
        cursor = coll.find(f(query, cls.s_bclass), _at_most=_at_most, _order=_order)
        if not _deserialize:
            return list(cursor)
        return [cls.s_bclass.deserialize_object(serialized_data, _coll_name) for serialized_data in cursor]

    def load_ids(self, query: f = None, _coll_name: str = None, _at_most: int = 0, _order: dict = None, as_of: datetime = None) -> list[ID]:
        # Use instance as_of_time if not provided
        cls = self.traitable_class
        as_of = as_of or self.as_of_time

        if as_of is not None:
            # Load from history collection
            history_coll = self.history_collection(_coll_name=_coll_name)
            if history_coll:
                # Add time filter to query
                from core_10x.trait_filter import f

                time_query = f(**{'_at': {'$lte': as_of}})
                combined_query = f(query, cls.s_bclass) & time_query if query else time_query
                cursor = history_coll.find(combined_query, _at_most=_at_most, _order=_order)
                id_tag = history_coll.s_id_tag
                return [ID(serialized_data.get(id_tag), _coll_name) for serialized_data in cursor]
            return []

        coll = self.collection(_coll_name=_coll_name)
        id_tag = coll.s_id_tag
        cursor = coll.find(query, _at_most=_at_most, _order=_order)
        return [ID(serialized_data.get(id_tag), _coll_name) for serialized_data in cursor]

    def delete_collection(self, _coll_name: str = None) -> bool:
        cls = self.traitable_class
        store = cls.store()
        if not store:
            return False
        cname = _coll_name or PackageRefactoring.find_class_id(cls)
        return store.delete_collection(collection_name=cname)

    def save(self, traitable_instance) -> RC:
        rc = traitable_instance.verify()
        if not rc:
            return rc

        rc = traitable_instance.share(False)  # -- not accepting existing entity values, if any
        if not rc:
            return rc

        serialized_data = traitable_instance.serialize_object()
        if not serialized_data:  # -- it's a lazy instance - no reason to load and re-save
            return RC_TRUE

        coll = self.collection()
        if not coll:
            return RC(False, f'{self.__class__} - no store available')

        try:
            # Save to main collection
            rev = coll.save(serialized_data.copy())  # copy to prevent modifications in filter builder TODO: fix

            if traitable_instance.s_keep_history:
                TraitableHistory.save_history(serialized_data, self.traitable_class.store(), self.history_collection())

        except Exception as e:
            return RC(False, str(e))

        traitable_instance.set_revision(rev)
        return RC_TRUE

    def delete(self, traitable_instance: Traitable) -> RC:
        rc = self.delete_in_store(traitable_instance.id())
        if rc:
            traitable_instance.set_revision(0)
        return rc


class TraitableHistory:
    """Special collection for storing traitable history with _at timestamp and _who fields."""

    # TODO: make this a traitable representing a history entry - perhaps a special traitable class for each traitable.
    @staticmethod
    def collection_name(cls, _coll_name: str = None) -> str:
        """Get the history collection name for a traitable class."""
        base_name = _coll_name or PackageRefactoring.find_class_id(cls)
        return f'{base_name}#history'

    @staticmethod
    def save_history(serialized_data: dict, store: TsStore, history_coll: TsCollection) -> None:
        data = serialized_data.copy()
        data |= {
            '_id': uuid.uuid1().hex,  # TODO: exogenous_id
            '_who': store.auth_user(),
            '_traitable_id': data.pop('_id'),
            '_traitable_rev': data.pop('_rev'),
        }
        history_coll.save_new(
            {
                '$set': data,
                '$currentDate': {'_at': True},
            }
        )

    @staticmethod
    def history(cls, _at_most: int = -1, _filter: f = None, **named_filters) -> list[dict]:
        """Get history entries for a traitable class."""
        history_coll = cls.s_storage_helper.history_collection(cls)
        if not history_coll:
            return []

        cursor = history_coll.find(_filter=_filter, **named_filters)
        cursor = cursor.sort('_at', direction=-1)  # Most recent first

        if _at_most >= 0:
            cursor = cursor.limit(_at_most)

        return list(cursor)

    @staticmethod
    def latest_revision(cls, entity_id) -> dict | None:
        """Get the latest revision of an entity from history."""
        history_coll = cls.s_storage_helper.history_collection(cls)
        if not history_coll:
            return None

        id_tag = '_traitable_id'
        cursor = history_coll.find(**{id_tag: entity_id})
        cursor = cursor.sort('_at', direction=-1)
        cursor = cursor.limit(1)

        for entry in cursor:
            return entry

        return None

    @staticmethod
    def restore(cls, entity_id: ID, timestamp: datetime = None) -> RC:
        """Restore an entity to a specific point in time."""
        id_tag = '_traitable_id'

        if timestamp is None:
            # Restore to latest revision
            history_entry = TraitableHistory.latest_revision(cls, entity_id)
        else:
            # Find the most recent entry before or at the specified time
            history_coll = cls.s_storage_helper.history_collection(cls, _coll_name=entity_id.collection_name)
            if not history_coll:
                return RC(f'No history collection found for {entity_id}')

            query = f(**{id_tag: entity_id, '_at': {'$lte': timestamp}})
            cursor = history_coll.find(query)
            cursor = cursor.sort('_at', direction=-1)
            cursor = cursor.limit(1)

            history_entry = None
            for entry in cursor:
                history_entry = entry
                break

        if not history_entry:
            return RC(f'No history entry found for {entity_id}, timestamp {timestamp}')

        # Remove history-specific fields and restore the entity
        entity_data = history_entry.copy()
        del entity_data['_at']
        del entity_data['_who']
        entity_data['_id'] = entity_data.pop(id_tag, None)
        entity_data['_rev'] = entity_data.pop('_traitable_rev', None)

        serialized_dict = {
            Nucleus.CLASS_TAG(): entity_id.collection_name or PackageRefactoring.find_class_id(cls),
            # Nucleus.TYPE_TAG(): Nucleus.NX_RECORD_TAG(),
            # Nucleus.OBJECT_TAG(): entity_data
            '_type': '_nx',
            '_obj': entity_data,
        }
        try:
            traitable = Nucleus.deserialize_dict(serialized_dict)
        except Exception as e:
            return RC(f'Could not deserialize {entity_id}: {e}')

        if not traitable:
            return RC(f'Could not deserialize {entity_id}: {traitable}')

        return traitable.save()


@dataclass
class AsOfContext:
    """Context manager for time-based entity loading."""

    # TODO: generalize so that context created on baseclass applies to all subclasses
    traitable_class: type[Traitable]
    as_of_time: datetime
    _original_as_of_time: datetime = None

    def __enter__(self):
        # Store original as_of_time and set new one
        self._original_as_of_time = self.traitable_class.s_storage_helper.as_of_time
        self.traitable_class.s_storage_helper.as_of_time = self.as_of_time
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original as_of_time
        self.traitable_class.s_storage_helper.as_of_time = self._original_as_of_time


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
        return self.data_type.instance_by_id(s)

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
