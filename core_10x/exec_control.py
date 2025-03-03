import functools

from core_10x_i import BTraitableProcessor as BTP


def GRAPH_ON(debug: bool = -1, convert_values: bool = -1):
    return BTP.create(1, convert_values, debug)

def GRAPH_OFF(debug: bool = -1, convert_values: bool = -1):
    return BTP.create(0, convert_values, debug)

def DEBUG_ON(convert_values: bool = -1):
    return BTP.create(-1, convert_values, 1)

def DEBUG_OFF(convert_values: bool = -1):
    return BTP.create(-1, convert_values, 0)

def CONVERT_VALUES_ON(debug: bool = -1):
    return BTP.create(-1, 1, debug)

def CONVERT_VALUES_OFF(debug: bool = -1):
    return BTP.create(-1, 0, debug)
