from functools import partial

from core_10x_i import BTraitableProcessor as BTP

def _create(flags, debug=None, convert_values=None):
    if debug or debug is None and BTP.current().flags() & BTP.DEBUG:
        flags |= BTP.DEBUG
    elif convert_values or convert_values is None and BTP.current().flags() & BTP.CONVERT_VALUES:
        flags |= BTP.CONVERT_VALUES
    return BTP.create(flags)

GRAPH_ON = partial(_create, BTP.ON_GRAPH)
GRAPH_OFF= partial(_create, 0)
