import importlib

import pytest
import xxcommon.curve

import xxfin.cxx_rate_curve
import xxfin.day_count_convention
import xxfin.ir_compounding
import xxfin.py_rate_curve
import xxfin.rate_curve

#-- Every module the fixtures below re-import. Their namespaces are snapshotted and put back
#-- verbatim on exit (see use_cxx) rather than re-imported: re-running the module bodies would
#-- resolve against the *current* flags, and this suite runs with use_cxxfin deliberately True
#-- while day_count_convention / ir_compounding are still bound to the py implementations they
#-- imported before the conftest flipped it. Restoring the snapshot also keeps the original class
#-- objects alive, so modules that captured them at import (e.g. ir_zero_rate_curve) stay coherent.
_SWAPPED_MODULES = (
    xxcommon.curve,
    xxfin.day_count_convention,
    xxfin.ir_compounding,
    xxfin.py_rate_curve,
    xxfin.cxx_rate_curve,
    xxfin.rate_curve,
)


@pytest.fixture
def cxx_or_py_rates_curve(use_cxx, cxx_or_py_cxx_rate_curve):
    importlib.reload(xxfin.rate_curve)
    from xxfin.cxx_rate_curve import RateCurve as CxxRateCurve
    from xxfin.py_rate_curve import RateCurve as PyRateCurve

    assert xxfin.rate_curve.RateCurve is (CxxRateCurve if use_cxx else PyRateCurve)
    assert issubclass(xxfin.rate_curve.RateCurve, xxfin.py_rate_curve.RateCurve)
    yield


@pytest.fixture
def cxx_or_py_cxx_rate_curve(cxx_or_py_py_rate_curve):
    importlib.reload(xxfin.cxx_rate_curve)
    yield


@pytest.fixture
def cxx_or_py_py_rate_curve(cxx_or_py_xxcommon_curve, cxx_or_py_day_count_convention, cxx_or_py_ir_compounding):
    import xxfin.py_rate_curve

    importlib.reload(xxfin.py_rate_curve)
    assert issubclass(xxfin.py_rate_curve.RateCurve, xxcommon.curve.DateCurve)
    yield


@pytest.fixture
def cxx_or_py_xxcommon_curve(use_cxx):
    importlib.reload(xxcommon.curve)
    from xxcommon.cxx_curve import DateCurve as CxxDateCurve
    from xxcommon.py_curve import DateCurve as PyDateCurve

    assert xxcommon.curve.DateCurve is (CxxDateCurve if use_cxx else PyDateCurve)
    yield


@pytest.fixture
def cxx_or_py_ir_compounding(use_cxx):
    importlib.reload(xxfin.ir_compounding)
    from xxfin.cxx_ir_compounding import COMPOUNDING as CXX_COMPOUNDING
    from xxfin.py_ir_compounding import COMPOUNDING as PY_COMPOUNDING

    assert xxfin.ir_compounding.COMPOUNDING is (CXX_COMPOUNDING if use_cxx else PY_COMPOUNDING)
    yield


@pytest.fixture
def cxx_or_py_day_count_convention(use_cxx):
    importlib.reload(xxfin.day_count_convention)
    from xxfin.cxx_day_count_convention import DAY_COUNT_CONVENTION as CXX_DAY_COUNT_CONVENTION
    from xxfin.py_day_count_convention import DAY_COUNT_CONVENTION as PY_DAY_COUNT_CONVENTION

    assert xxfin.day_count_convention.DAY_COUNT_CONVENTION is (CXX_DAY_COUNT_CONVENTION if use_cxx else PY_DAY_COUNT_CONVENTION)
    yield


@pytest.fixture(params=[False, True], ids=['py', 'cxx'])
def use_cxx(request):
    from xxcommon.xxcommon_env_vars import XXCommonEnvVars

    from xxfin.xxfin_env_vars import XXFinEnvVars

    saved_flags = (XXCommonEnvVars.use_cxx_curve, XXFinEnvVars.use_cxxfin)
    saved_namespaces = [(module, dict(module.__dict__)) for module in _SWAPPED_MODULES]

    use_cxx = XXCommonEnvVars.use_cxx_curve = XXFinEnvVars.use_cxxfin = request.param
    try:
        yield use_cxx
    finally:
        #-- Undo BOTH halves of the swap, or a [cxx] leg silently reconfigures every later test in
        #-- the same worker: the flags are process-global and read at runtime by consumers outside
        #-- _SWAPPED_MODULES (AADCContext gates its interpolator patch on use_cxx_curve), while the
        #-- reloads leave cxx classes bound in modules whose flags now say py. This lives here, not
        #-- in each fixture, because use_cxx is the root dependency and so tears down last -- after
        #-- every per-module fixture has finished reloading.
        XXCommonEnvVars.use_cxx_curve, XXFinEnvVars.use_cxxfin = saved_flags
        for module, namespace in saved_namespaces:
            module.__dict__.clear()
            module.__dict__.update(namespace)
