from py10x_kernel import BProcessContext
from py10x_kernel import BTraitableProcessor as BTP  # noqa: N817
from py10x_kernel import TID

from core_10x.trait import BoundTrait

# TODO: consider splitting rename DEBUG into TYPE_CHECK and EAGER_LOAD.
# TODO: consider making CONVERT/TYPE_CHECK mode default.


def CHANGE_MODE(debug: bool = -1, convert_values: bool = -1):  # noqa: N802
    return BTP.create(-1, convert_values, debug, True, False)


def DEFAULT_CACHE(debug: bool = -1, convert_values: bool = -1):  # noqa: N802
    return BTP.create(0, convert_values, debug, False, True)


def GRAPH_ON(debug: bool = -1, convert_values: bool = -1):  # noqa: N802
    return BTP.create(1, convert_values, debug, False, False)


def GRAPH_OFF(debug: bool = -1, convert_values: bool = -1):  # noqa: N802
    return BTP.create(0, convert_values, debug, False, False)


def DEBUG_ON(convert_values: bool = -1):  # noqa: N802
    return BTP.create(-1, convert_values, 1, True, False)


def DEBUG_OFF(convert_values: bool = -1):  # noqa: N802
    return BTP.create(-1, convert_values, 0, True, False)


def CONVERT_VALUES_ON(debug: bool = -1):  # noqa: N802
    return BTP.create(-1, 1, debug, True, False)


def CONVERT_VALUES_OFF(debug: bool = -1):  # noqa: N802
    return BTP.create(-1, 0, debug, True, False)


def INTERACTIVE():  # noqa: N802
    return BTP.create_interactive()


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
    def __init__(self, gp: BTP, bound_trait: BoundTrait, target_class, *target_trait_names):
        self.gp = gp
        obj = bound_trait.obj
        trait = bound_trait.trait
        self.deps_data = gp.find_dependencies(obj, trait, target_class, *target_trait_names)

    def perturb_value(self, obj_cls, obj_id, trait, value):
        cache = self.gp.cache()
        cache.perturb_existing_node(obj_cls.s_bclass, obj_id, trait, value)

    def deps(self, objects = True, trait_names = False):
        for cls, traits_by_id in self.deps_data.items():
            for id, traits in traits_by_id.items():
                obj = cls(_id = id) if objects else id
                for t in traits:
                    if trait_names:
                        t = t.name
                    yield (cls, obj, t)
