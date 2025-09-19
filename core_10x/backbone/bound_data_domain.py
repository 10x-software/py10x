from core_10x.backbone.backbone_traitable import RT, BackboneTraitable, T
from core_10x.data_domain import DataDomain
from core_10x.environment_variables import EnvVars
from core_10x.resource import Resource
from core_10x.xnone import XNone


class ResourceSpec(BackboneTraitable):
    # fmt: off
    build_area: str         = T(T.ID)
    name: str               = T(T.ID)
    resource_class: type    = T()
    resource_kwargs: dict   = T()

    resource: Resource      = RT()
    # fmt: on

    def build_area_get(self) -> str:
        return EnvVars.sdlc_area

    def name_get(self) -> str:
        kwargs = self.resource_kwargs
        return kwargs.get(Resource.HOSTNAME_TAG, XNone)

    def resource_get(self) -> Resource:
        cls = self.resource_class
        assert issubclass(cls, Resource), f'{cls} is not a subclass of Resource'
        return cls.instance(**self.resource_kwargs)


class BoundDataDomain(BackboneTraitable):
    # fmt: off
    domain: DataDomain.__class__    = T(T.ID)
    build_area: str                 = T(T.ID)
    bound_categories: dict          = T()
    # fmt: on

    def build_area_get(self) -> str:
        return EnvVars.sdlc_area

    def resource(self, category: str, throw: bool = True) -> Resource:
        r_spec_id: str = self.bound_categories.get(category)
        if not r_spec_id:
            if throw:
                raise ValueError(f'{self.domain} - unknown category {category}')
            return None

        r_spec = ResourceSpec(_id=r_spec_id)
        return r_spec.resource
