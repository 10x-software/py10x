import re

from core_10x.resource import TS_STORE, ResourceRequirements


def _raise_type_error(cls, **kwargs):
    raise TypeError(f'{cls} - subclassing is not allowed')

class DataDomain:
    s_dir = {}

    s_resource_requirements = {}
    def __init_subclass__(cls, **kwargs):
        name = cls.name()
        ed = DataDomain.s_dir.get(name)
        assert ed is None, f"DataDomain '{name}' is already registered in {ed}"
        DataDomain.s_dir[name] = cls

        cls.__init_subclass__ = lambda **kwargs: _raise_type_error(cls, **kwargs)
        category: str
        rrs = cls.s_resource_requirements
        for category, resource_reqs in cls.__dict__.items():
            if isinstance(resource_reqs, ResourceRequirements):
                assert category.isupper(), f"Category '{category}' must be an uppercase name"
                resource_reqs.domain = cls
                resource_reqs.category = category
                rrs[category] = resource_reqs

        assert rrs, f"DataDomain '{cls} must define at least one category"

    @classmethod
    def name(cls: str) -> str:
        return re.sub(r'([a-z])([A-Z])', r'\1_\2', cls.__qualname__).upper()

    @classmethod
    def resource_requirement(cls, category: str, throw = True) -> ResourceRequirements:
        rr = cls.s_resource_requirements.get(category)
        if rr is None and throw:
            raise ValueError(f"DataDomain {cls} - unknown category '{category}'")

        return rr

class GeneralDomain(DataDomain):
    GENERAL = TS_STORE()
    ...

