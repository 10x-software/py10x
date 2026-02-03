from core_10x.traitable import Traitable, Trait, T, RT, RC, XNone

class TraitableHeir(Traitable):
    _grantor: Traitable = T()

    s_grantor_traits = {}
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        cls.s_grantor_traits = dir = {}
        grantor_trait = cls.trait('_grantor')
        trait: Trait
        for trait in cls.traits():
            if trait is grantor_trait or trait.flags_on(T.RESERVED):
                continue
            if not trait.has_custom_getter() and trait.default is XNone:   #-- trait has neither getter nor default value
                trait.set_f_get(lambda self, trait_name = trait.name: self.heir_getter(trait_name), False)
                dir[trait.name] = trait

    def heir_getter(self, trait_name: str):
        grantor = self._grantor
        if not grantor:
            return XNone
        trait = grantor.__class__.trait(trait_name)
        return grantor.get_value(trait) if trait else XNone

    def serialize_object(self, save_references = False) -> dict:
        serialized_data = super().serialize_object(save_references = save_references)
        for name, trait in self.__class__.s_grantor_traits.items():
            if not self.is_set(trait):
                del serialized_data[name]

        return serialized_data
