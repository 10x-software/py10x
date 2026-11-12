from py10x_kernel import BProcessContext
from py10x_kernel import BTraitableProcessor as BTP  # noqa: N817
from py10x_kernel import UpwardDepsOff as _UpwardDepsOff

from core_10x.trait import BoundTrait, Trait
from core_10x.traitable_id import ID

# TODO: consider splitting rename DEBUG into TYPE_CHECK and EAGER_LOAD.
# TODO: consider making CONVERT/TYPE_CHECK mode default.


class ExecControl:
    #-- a class, so the whole family has one class id: PackageRefactoring tracks classes, not free functions
    @staticmethod
    def change_mode(debug: bool = -1, convert_values: bool = -1):
        return BTP.create(-1, convert_values, debug, True, False)

    @staticmethod
    def default_cache(debug: bool = -1, convert_values: bool = -1):
        return BTP.create(0, convert_values, debug, False, True)

    @staticmethod
    def graph_on(debug: bool = -1, convert_values: bool = -1):
        return BTP.create(1, convert_values, debug, False, False)

    @staticmethod
    def graph_off(debug: bool = -1, convert_values: bool = -1):
        return BTP.create(0, convert_values, debug, False, False)

    @staticmethod
    def upward_deps_off():
        """
        Stays on-graph, but effectively cuts off dependency chain upwards
        """
        return _UpwardDepsOff()

    @staticmethod
    def debug_on(convert_values: bool = -1):
        return BTP.create(-1, convert_values, 1, True, False)

    @staticmethod
    def debug_off(convert_values: bool = -1):
        return BTP.create(-1, convert_values, 0, True, False)

    @staticmethod
    def convert_values_on(debug: bool = -1):
        return BTP.create(-1, 1, debug, True, False)

    @staticmethod
    def convert_values_off(debug: bool = -1):
        return BTP.create(-1, 0, debug, True, False)

    @staticmethod
    def interactive():
        return BTP.create_interactive()


# fmt: off
CHANGE_MODE         = ExecControl.change_mode
DEFAULT_CACHE       = ExecControl.default_cache
GRAPH_ON            = ExecControl.graph_on
GRAPH_OFF           = ExecControl.graph_off
UPWARD_DEPS_OFF     = ExecControl.upward_deps_off
DEBUG_ON            = ExecControl.debug_on
DEBUG_OFF           = ExecControl.debug_off
CONVERT_VALUES_ON   = ExecControl.convert_values_on
CONVERT_VALUES_OFF  = ExecControl.convert_values_off
INTERACTIVE         = ExecControl.interactive
# fmt: on


# noinspection PyMethodOverriding
class ProcessContext(BProcessContext):
    @staticmethod
    def set_flags(flags: int) -> int:
        old_flags = BProcessContext.BPC.flags()
        BProcessContext.BPC.set_flags(flags)
        return old_flags

    @staticmethod
    def reset_flags(flags: int) -> int:
        old_flags = BProcessContext.BPC.flags()
        BProcessContext.BPC.reset_flags(flags)
        return old_flags

    @staticmethod
    def replace_flags(flags: int) -> int:
        old_flags = BProcessContext.BPC.flags()
        BProcessContext.BPC.replace_flags(flags)
        return old_flags

    @staticmethod
    def flags() -> int:
        return BProcessContext.BPC.flags()


class FlagsContext:
    s_default_flags = 0

    def __init__(self, flags=None):
        self._flags = flags if flags is not None else self.s_default_flags

    def __enter__(self):
        self._old_flags = ProcessContext.set_flags(self._flags)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        ProcessContext.BPC.replace_flags(self._old_flags)


class CACHE_ONLY(FlagsContext):
    s_default_flags = ProcessContext.CACHE_ONLY


class GraphDeps:
    def __init__(self, gp: BTP, bound_trait: BoundTrait, inputs_spec: dict[type, tuple[str, ...]]):
        self.gp = gp
        obj = bound_trait.obj
        trait = bound_trait.trait
        self.deps_data = gp.find_dependencies(obj, trait, inputs_spec)

    def read(self, traitable_cls, obj_id: ID, trait: Trait):
        cache = self.gp.cache()
        return cache.read_existing_node(traitable_cls.s_bclass, obj_id, trait)

    def perturb(self, traitable_cls, obj_id: ID, trait: Trait, value):
        cache = self.gp.cache()
        cache.perturb_existing_node(traitable_cls.s_bclass, obj_id, trait, value)

    def perturb_value(self, traitable, trait_name: str, value):
        obj_cls = traitable.__class__
        trait = obj_cls.trait(trait_name, throw=True)
        self.perturb(obj_cls, traitable.id(), trait, value)

    def deps(self, objects=True, trait_names=False):
        for cls, traits_by_id in self.deps_data.items():
            for id, traits in traits_by_id.items():
                obj = cls(_id=id) if objects else id
                for t, value in traits:
                    if trait_names:
                        t = t.name
                    yield (cls, obj, t, value)
