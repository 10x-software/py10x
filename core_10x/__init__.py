from os import path

pp = path.dirname(path.abspath(__file__))
path_to_core_10x = path.dirname(pp)

from core_10x_i import PyLinkage, XCache

PyLinkage.init(path_to_core_10x)

class _Finalizer:
    def __del__(self):
        # release references to python objects that have to be deleted before the interpreter exits
        XCache.clear()
        PyLinkage.clear()

_finalizer = _Finalizer()
