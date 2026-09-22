import aadc
from aadc.numpy_compat.other_functions import interpolate_1d
from xxcommon.curve import CurveParams
from xxcommon.xxcommon_env_vars import XXCommonEnvVars

import xxfin.root_solver as _root_solver


class _AadcRootResult:
    converged  = True
    flag       = 'converged'
    iterations = 0


def _aadc_root_scalar(f, bracket, xtol, method):
    aadc.root_scalar(f, x0 = 0., xtol = xtol)
    return _AadcRootResult()


def _aadc_interp1d(x, y, **kwargs):
    def _f(x0):
        return interpolate_1d(x0, x, y)
    return _f


class AADCDomainSwap:
    """
    Swaps two domain-specific implementations for AADC-aware ones -- curve interpolation and
    root-solving -- neither of which callable_instrumentation's registry covers (both are
    object-attribute/module-level function swaps, not name-based call redirection). Session-scoped:
    entered/exited once by AadcExec, not once per AadcKernel.build(). Does NOT patch builtins/math.*
    anymore -- that's now handled surgically, per instrumented function, by AadcCallableRewriter.
    """

    def __enter__(self):
        if not XXCommonEnvVars.use_cxx_curve:
            self._saved_interpolator         = CurveParams.DEFAULT_INTERPOLATOR
            CurveParams.DEFAULT_INTERPOLATOR = _aadc_interp1d
        self._saved_root_scalar          = _root_solver.root_scalar_impl
        _root_solver.root_scalar_impl    = _aadc_root_scalar
        return self

    def __exit__(self, *args):
        _root_solver.root_scalar_impl    = self._saved_root_scalar
        if not XXCommonEnvVars.use_cxx_curve:
            CurveParams.DEFAULT_INTERPOLATOR = self._saved_interpolator
