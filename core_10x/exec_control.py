from core_10x_i import BProcessContext
from core_10x_i import BTraitableProcessor as BTP  # noqa: N817

#TODO: rename DEBUG to TYPE_CHECK?
#TODO: make CONVERT/DEBUG mode default?

def CHANGE_MODE(debug: bool = -1, convert_values: bool = -1): # noqa: N802
    return BTP.create(-1, convert_values, debug, True, False)

def DEFAULT_CACHE(debug: bool = -1, convert_values: bool =-1): # noqa: N802
    return BTP.create(0, convert_values, debug, False, True)

def GRAPH_ON(debug: bool = -1, convert_values: bool = -1): # noqa: N802
    return BTP.create(1, convert_values, debug, False, False)

def GRAPH_OFF(debug: bool = -1, convert_values: bool = -1): # noqa: N802
    return BTP.create(0, convert_values, debug, False, False)

def DEBUG_ON(convert_values: bool = -1): # noqa: N802
    return BTP.create(-1, convert_values, 1, True, False)

def DEBUG_OFF(convert_values: bool = -1): # noqa: N802
    return BTP.create(-1, convert_values, 0, True, False)

def CONVERT_VALUES_ON(debug: bool = -1): # noqa: N802
    return BTP.create(-1, 1, debug, True, False)

def CONVERT_VALUES_OFF(debug: bool = -1): # noqa: N802
    return BTP.create(-1, 0, debug, True, False)

def INTERACTIVE(): # noqa: N802
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

