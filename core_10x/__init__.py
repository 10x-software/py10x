from core_10x_i import PyLinkage, BCache
from core_10x.xnone import XNone
from core_10x.rc import RC_TRUE
from core_10x.trait import TraitMethodError

PyLinkage.init(XNone, RC_TRUE, TraitMethodError)
PyLinkage.redirect_stdout_to_python()

class _Finalizer:
    def __del__(self):
        # release references to python objects that have to be deleted before the interpreter exits
        BCache.clear()
        PyLinkage.clear()

_finalizer = _Finalizer()
