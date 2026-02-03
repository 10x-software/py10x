from core_10x.traitable import Traitable, Trait, T, XNone

class TraitableHeir(Traitable):
    _grantor: Traitable = T()

    s_grantor_traits = {}
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        def heir_getter(grantor: Traitable, trait_name: str):
            trait = grantor.__class__.trait(trait_name)
            return grantor.get_value(trait) if trait else XNone

        cls.s_grantor_traits = dir = {}
        grantor_trait = cls.trait('_grantor')
        trait: Trait
        for trait in cls.traits():
            if trait is grantor_trait or trait.flags_on(T.RESERVED):
                continue
            if not trait.flags_on(T.CUSTOM_GET) and trait.default is XNone:   #-- trait has neither getter nor default value
                trait.set_f_get(lambda obj, trait_name = trait.name: heir_getter(obj.get_value(grantor_trait), trait_name), True)
                dir[trait.name] = trait

    def serialize_object(self, save_references = False) -> dict:
        serialized_data = super().serialize_object(save_references = save_references)
        return { name: serialized_data[name] for name in self.__class__.s_grantor_traits.keys() }
