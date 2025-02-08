import inspect
# import uuid
# import hashlib
# import copy

from core_10x_i import BTraitable, BTraitableClass

from core_10x.xnone import XNone
from core_10x.trait_definition import TraitDefinition, TraitModification
from core_10x.trait import Trait, TRAIT_METHOD, T, BoundTrait, trait_value
import core_10x.concrete_traits
from core_10x.global_cache import cache
from core_10x.rc import RC, RC_TRUE
from core_10x.package_refactoring import PackageRefactoring


class TraitAccessor:
    def __init__(self, obj: 'Traitable'):
        self.cls = obj.__class__
        self.obj = obj

    def __getattr__(self, trait_name: str) -> BoundTrait:
        trait = self.cls.trait(trait_name, throw = True)
        return BoundTrait(self.obj, trait)

    def __call__(self, trait_name: str, throw = True) -> Trait:
        return self.cls.trait(trait_name, throw = True)

#-- TODO: also derive from Nucleus!
class Traitable(BTraitable):

    s_dir = {}
    @classmethod
    @cache
    def build_trait_dir(cls, class_dict: dict = None, annotations: dict = None ) -> RC:
        if class_dict is None:
            class_dict = cls.__dict__
        if annotations is None:
            annotations = inspect.get_annotations(cls)

        rc = RC(True)
        cls.s_dir = dir = dict(cls.s_dir)       #-- shallow copy!

        for trait_name, trait_def in class_dict.items():
            if not isinstance(trait_def, TraitDefinition):
                continue

            dt = annotations.get(trait_name, XNone)
            if isinstance(trait_def, TraitModification):
                old_trait: Trait = dir.get(trait_name)
                if not old_trait:
                    rc <<= f'{trait_name} = M(...), but the trait is unknown'

                trait_def.apply(old_trait.t_def)
                if dt is not XNone:     #-- the data type is also being modified
                    trait_def.data_type = dt

            else:
                trait_def.data_type = dt

            trait_def.name = trait_name

            trait = Trait.create(trait_name, trait_def, class_dict, annotations, rc)
            dir[trait_name] = trait

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
        'trait',
        '_default_cache',
    )
    def __init_subclass__(cls, **kwargs):
        cls.build_trait_dir().throw(exc = TypeError)
        for trait_name, trait in cls.s_dir.items():
            setattr(cls, trait_name, trait)

        cls.s_bclass = BTraitableClass(cls)
        cls.__slots__ = ( *cls.s_special_attributes, *tuple(cls.s_dir.keys()) )

    def __init__(self, **trait_values):
        super().__init__(self.s_bclass, **trait_values)
        self.trait = TraitAccessor(self)

    def get_value_by_name(self, trait_name: str, *args):
        trait = self.__class__.trait(trait_name)
        return self.get_value(trait) if not args else self.get_value(trait, args)

    def set_value_by_name(self, trait_name: str, value, *args) -> RC:
        trait = self.__class__.trait(trait_name)
        return self.set_value(trait, value) if not args else self.get_value(trait, value, args)

    # def def_trait_invalidate(self, trait_def: TraitDefinition):
    #     self._default_cache.trait_invalidate(trait_def)
    #
    # def def_trait_get(self, trait_def: TraitDefinition):
    #     self._default_cahe.trait_get(trait_def)


    # @classmethod
    # @cache
    # def id_trait_defs(cls) -> dict:
    #     return { name: trait_def for name, trait_def in cls.s_traitdef_dir.items() if trait_def.flags.on(T.ID) }

    # @classmethod
    # def new_exogenous_id(cls) -> str:
    #     return uuid.uuid1().hex
    #
    # @classmethod
    # def hash_str(cls, unhashed: str) -> str:
    #     return hashlib.md5(''.join(unhashed).encode(), usedforsecurity = False).hexdigest()

    # s_id_delimiter = '|'
    # @classmethod
    # def create_id(cls, trait_values: dict) -> str:
    #     id_trait_defs = cls.id_trait_defs()
    #     if not id_trait_defs:
    #         return cls.new_exogenous_id()
    #
    #     rc = RC(True)
    #     regulars = []
    #     to_hash = []
    #     for name, trait_def in id_trait_defs.items():
    #         value = trait_values.get(name, trait_values)
    #         if value is not trait_values:
    #             serialized_value = trait_def.serialize(value)   #-- TODO: revisit for entity traits and maybe others!
    #             str_value = str(serialized_value)
    #             res = to_hash if trait_def.flags.on(T.HASH) else regulars
    #             res.append(str_value)
    #         else:
    #             rc.add_error(f'- {name}')
    #
    #     if not rc:
    #         raise RuntimeError('\n'.join(( f'{cls}: ID traits are missing:', *rc.payload) ))
    #
    #     if to_hash:
    #         regulars.append(cls.hash_str(''.join(to_hash)))
    #
    #     return cls.s_id_delimiter.join(regulars)

    #===================================================================================================================
    #   Default getters/setters
    #===================================================================================================================
    # def raw_set_value(self, trait: Trait, value) -> RC:
    #
    #     return RC.TRUE
