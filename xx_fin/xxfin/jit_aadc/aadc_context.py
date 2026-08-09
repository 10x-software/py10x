import builtins
import math as _stdlib_math

import aadc
from aadc import record_kernel
from aadc.numpy_compat.other_functions import interpolate_1d
from xxcommon.curve import CurveParams
from xxcommon.xxcommon_env_vars import XXCommonEnvVars

import xxfin.root_solver as _root_solver
from xxfin.xxfin_env_vars import XXFinEnvVars


class _AadcRootResult:
    converged  = True
    flag       = 'converged'
    iterations = 0


def _aadc_root_scalar(f, bracket, xtol, method):
    aadc.root_scalar(f, x0=0., xtol=xtol)
    return _AadcRootResult()


def _aadc_interp1d(x, y, **kwargs):
    def _f(x0):
        return interpolate_1d(x0, x, y)
    return _f


class AADCContext:
    def __enter__(self):
        #-- patch stdlib math with aadc equivalents
        self._math_saved = {}
        for name in vars(aadc.math):
            if not name.startswith('_') and hasattr(_stdlib_math, name):
                self._math_saved[name] = getattr(_stdlib_math, name)
                setattr(_stdlib_math, name, getattr(aadc.math, name))

        #-- patch builtins with aadc equivalents
        self._builtins_saved = {}
        for name in ('min', 'max', 'abs'):
            if hasattr(aadc.math, name):
                self._builtins_saved[name] = getattr(builtins, name)
                setattr(builtins, name, getattr(aadc.math, name))

        #-- patch domain-specific items
        if not XXCommonEnvVars.use_cxx_curve:
            self._saved_interpolator         = CurveParams.DEFAULT_INTERPOLATOR
            CurveParams.DEFAULT_INTERPOLATOR = _aadc_interp1d
        self._saved_root_scalar          = _root_solver.root_scalar_impl
        _root_solver.root_scalar_impl    = _aadc_root_scalar

        self._kernel_ctx = record_kernel()
        return self._kernel_ctx.__enter__()

    def __exit__(self, *args):
        result = self._kernel_ctx.__exit__(*args)

        for name, val in self._math_saved.items():
            setattr(_stdlib_math, name, val)

        for name, val in self._builtins_saved.items():
            setattr(builtins, name, val)

        _root_solver.root_scalar_impl    = self._saved_root_scalar
        if not XXCommonEnvVars.use_cxx_curve:
            CurveParams.DEFAULT_INTERPOLATOR = self._saved_interpolator
        return result
