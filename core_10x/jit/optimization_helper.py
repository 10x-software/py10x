from core_10x.traitable import Traitable, T, RC, RC_TRUE, ID

class OptimizationHelper(Traitable):
    traitable_class: type[Traitable]    = T(T.ID)
    objects_by_attr_name: dict          = T()

    def add_object(self, obj: Traitable, attr_name: str = '', _override = True, _save = True) -> RC:
        cls = self.traitable_class
        if not isinstance(obj, cls):
            return RC(False, f'{obj} is not an instance of {cls}')

        if attr_name:
            attr = getattr(cls, attr_name, None)
            if attr is None:
                return RC(False, f'{cls.__name__}: unknown attribute {attr_name}')

        data = self.objects_by_attr_name
        if not _override and data.get(attr_name) is not None:
            return RC(False, f'{cls.__name__}.{attr_name} - helper object already set')

        store_obj = cls.is_storable()
        if store_obj:
            rc = obj.save()
            if not rc:
                return rc
            data[attr_name] = obj.id_value()
        else:
            data[attr_name] = { trait.name: obj.get_trait_value(trait) for trait in cls.traits(flags_off = T.RESERVED) if obj.is_set(trait) }

        self.objects_by_attr_name = data
        return RC_TRUE if not _save else self.save()

    def get_object(self, attr_name: str = '', _fallback = True) -> Traitable:
        data = self.objects_by_attr_name
        trait_values = data.get(attr_name)
        if trait_values is None:
            if _fallback:
                trait_values = data.get('')
                if trait_values is None:
                    return None

        if isinstance(trait_values, str):   #-- id it is
            return self.traitable_class(_id = ID(id_value = trait_values))

        if isinstance(trait_values, dict):
            return self.traitable_class(**trait_values)

        return None

    @classmethod
    def add_helper(cls, traitable_class: type[Traitable], obj: Traitable, attr_name: str = '') -> RC:
        assert issubclass(traitable_class, Traitable), f'{traitable_class} must be a subclass of Traitable'
        oh = cls(traitable_class = traitable_class)
        return oh.add_object(obj, attr_name = attr_name)

    @classmethod
    def get_helper(cls, traitable_class: type[Traitable], attr_name: str = '') -> Traitable:
        oh = cls.existing_instance(traitable_class = traitable_class, _throw = False)
        return oh.get_object(attr_name = attr_name) if oh else None
