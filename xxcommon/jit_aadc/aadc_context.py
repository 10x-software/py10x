import builtins
import math as _stdlib_math

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
    Swaps domain-specific implementations for AADC-aware ones during the recording pass -- curve
    interpolation, root-solving, and (globally) math.*/builtins.abs/min/max. Scoped to exactly the
    recording pass (entered around record_kernel() inside AadcKernel.build()), NOT the whole AadcExec
    session -- plain-Python computation elsewhere in the session must never see these swapped
    implementations, or its results would silently diverge from unrecorded code.

    math.*/builtins patching is global, not per-function AST rewriting -- deliberately, so it has no
    blind spots: any plain function reached during recording, Traitable method or not, sees the patch
    (callable_instrumentation's per-function rewriting can only cover functions its target_base_classes/
    known_modules actually reach, which is unenumerable in practice). Safe only because the scope is
    this narrow -- the whole process briefly sees AADC-aware math during the literal tape-recording
    call, nothing else.
    """

    def __enter__(self):
        self._math_saved = {}
        for name in vars(aadc.math):
            if not name.startswith('_') and hasattr(_stdlib_math, name):
                self._math_saved[name] = getattr(_stdlib_math, name)
                setattr(_stdlib_math, name, getattr(aadc.math, name))

        self._builtins_saved = {}
        for name in ('min', 'max', 'abs'):
            if hasattr(aadc.math, name):
                self._builtins_saved[name] = getattr(builtins, name)
                setattr(builtins, name, getattr(aadc.math, name))

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

        for name, val in self._math_saved.items():
            setattr(_stdlib_math, name, val)
        for name, val in self._builtins_saved.items():
            setattr(builtins, name, val)
