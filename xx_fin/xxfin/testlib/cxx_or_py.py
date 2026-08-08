import importlib

import pytest
import xxcommon.curve

import xxfin.cxx_rate_curve
import xxfin.day_count_convention
import xxfin.ir_compounding
import xxfin.rate_curve


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

    use_cxx = XXCommonEnvVars.use_cxx_curve = XXFinEnvVars.use_cxxfin = request.param
    yield use_cxx
