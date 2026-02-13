# from os import path
#
# pp = path.dirname(path.abspath(__file__))
# path_to_core_10x = path.dirname(pp)
import atexit

from py10x_kernel import CORE_10X, PyLinkage, XCache


# fmt: off
def cleanup():
    XCache.clear()
    PyLinkage.clear()

atexit.register(cleanup)

PyLinkage.init({
    CORE_10X.PACKAGE_NAME:                              __name__,

    CORE_10X.XNONE_MODULE_NAME:                         'xnone',
    CORE_10X.XNONE_CLASS_NAME:                          'XNone',

    CORE_10X.RC_MODULE_NAME:                            'rc',
    CORE_10X.RC_TRUE_NAME:                              'RC_TRUE',

    CORE_10X.NUCLEUS_MODULE_NAME:                       'nucleus',
    CORE_10X.NUCLEUS_CLASS_NAME:                        'Nucleus',

    CORE_10X.ANONYMOUS_MODULE_NAME:                     'traitable',
    CORE_10X.ANONYMOUS_CLASS_NAME:                      'AnonymousTraitable',

    CORE_10X.TRAITABLE_ID_MODULE_NAME:                  'traitable_id',
    CORE_10X.TRAITABLE_ID_CLASS_NAME:                   'ID',

    CORE_10X.TRAIT_METHOD_ERROR_MODULE_NAME:            'trait_method_error',
    CORE_10X.TRAIT_METHOD_ERROR_CLASS_NAME:             'TraitMethodError',

    CORE_10X.PACKAGE_REFACTORING_MODULE_NAME:           'package_refactoring',
    CORE_10X.PACKAGE_REFACTORING_CLASS_NAME:            'PackageRefactoring',
    CORE_10X.PACKAGE_REFACTORING_FIND_CLASS:            'find_class',
    CORE_10X.PACKAGE_REFACTORING_FIND_CLASS_ID:         'find_class_id',
})

try:
    from dev_10x.version import __version__
except ImportError:
    __version__ = '0.0.0+unknown'  # fallback for dev envs

from core_10x.environment_variables import EnvVars
if EnvVars.graph_on:
    from core_10x.exec_control import GRAPH_ON

    go = GRAPH_ON()
    go.begin_using()
