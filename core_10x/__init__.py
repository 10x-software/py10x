from core_10x_i import PyLinkage
from core_10x.xnone import XNone
from core_10x.rc import RC_TRUE
from core_10x.trait import TraitMethodError

PyLinkage.init(XNone, RC_TRUE, TraitMethodError)
PyLinkage.redirect_stdout_to_python()
