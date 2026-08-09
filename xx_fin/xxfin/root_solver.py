from collections.abc import Callable

from core_10x.exec_control import UPWARD_DEPS_OFF
from core_10x.rc import RC, RC_TRUE
from scipy.optimize import root_scalar as _scipy_root_scalar

_DBG    = False

eps     = 1.e-15
bracket = (-1. + eps, 1. - eps)   ## TODO: set bracket by quotable class
method  = 'toms748'
xtol    = 1.e-12

def _default_root_scalar(f, bracket, xtol, method):
    return _scipy_root_scalar(f, bracket=bracket, xtol=xtol, method=method)

root_scalar_impl = _default_root_scalar    #-- swappable; e.g. replaced by AADCContext during recording

def ir_add_curve_point(f: Callable, bracket: tuple = bracket, xtol: float = xtol, method: str = method) -> RC:
    """
    :param f: a target function (it must utilize the root found, if any)
    :param bracket: [a,b], such that f(a) * f(b) < 0
    :param xtol: absolute tolerance
    :param method: root_scalar's method to use
    :return: convergence (success)
    """
    try:
        with UPWARD_DEPS_OFF():
            sol = root_scalar_impl(f, bracket = bracket, xtol = xtol, method = method)

        if sol.converged:
            if _DBG: print(f'num iterations: {sol.iterations}, root: {sol.root}')   # pragma: no cover
            return RC_TRUE

        if _DBG: print(f'status: {sol.flag}, num iterations: {sol.iterations}') # pragma: no cover
        return RC(False, f'No convergence for xtol = {xtol}')
    except Exception as e:
        return RC(False, str(e))
