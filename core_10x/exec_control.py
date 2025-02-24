from core_10x_i import BTraitableProcessor as BTP


def GRAPH_ON(debug = False, convert_values = False):
    flags = BTP.ON_GRAPH
    if debug:
        flags |= BTP.DEBUG
    elif convert_values:
        flags |= BTP.CONVERT_VALUES
    return BTP.create(flags)

def GRAPH_OFF(debug = False, convert_values = False):
    flags = 0
    if debug:
        flags |= BTP.DEBUG
    elif convert_values:
        flags |= BTP.CONVERT_VALUES
    return BTP.create(flags)
