from core_10x_i import BTraitableProcessor
from core_10x_i import SimpleCacheLayer

class XControl:
    @staticmethod
    def new_xcontrol(graph: bool, debug: bool, convert_values: bool) -> 'XControl':
        flags = 0x0
        if graph:
            flags |= BTraitableProcessor.ON_GRAPH
        if debug:
            flags |= BTraitableProcessor.DEBUG
        elif convert_values:
            flags |= BTraitableProcessor.CONVERT_VALUES

        return XControl(BTraitableProcessor.create(flags), graph)

    def __init__(self, btp: BTraitableProcessor, graph: bool):
        self.btp = btp
        if graph:
            cache = SimpleCacheLayer()
            self.btp.use_own_cache(cache)

    def __enter__(self):
        self.btp.begin_using()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.btp.end_using()

def GRAPH_ON(debug = False, convert_values = False):
    return XControl.new_xcontrol(True, debug, convert_values)

def GRAPH_OFF(debug = False, convert_values = False):
    return XControl.new_xcontrol(False, debug, convert_values)
