import pytest

import xxfin.py_ir_compounding as py

COMPOUNDING = None
COMPOUND_TRANSFORM = None
compounding_apply = None

_TR = [
    (0.0, 0.10),  # t=0: ACCRUAL_TO_RATE must return 0
    (0.5, 0.05),  # fractional year, small positive rate
    (1.0, 0.10),  # full year, typical rate
    (2.5, -0.02),  # fractional multi-year + mild negative rate
]


@pytest.fixture(autouse=True)
def rebind_globals(cxx_or_py_ir_compounding):
    global COMPOUNDING, COMPOUND_TRANSFORM, compounding_apply
    from xxfin.ir_compounding import COMPOUND_TRANSFORM, COMPOUNDING, compounding_apply

    yield


@pytest.mark.parametrize('comp_name', py.COMPOUNDING.all_names())
@pytest.mark.parametrize('transform_name', py.COMPOUND_TRANSFORM.all_names())
@pytest.mark.parametrize('t,r', _TR, ids=[f't={t}-r={r}' for t, r in _TR])
def test_matches_py(comp_name, transform_name, t, r):
    py_comp = getattr(py.COMPOUNDING, comp_name)
    py_tr = getattr(py.COMPOUND_TRANSFORM, transform_name)
    v = {py_tr.RATE_TO_ACCRUAL: r}.get(py_tr, py.compounding_apply(py_comp, py_tr.RATE_TO_ACCRUAL, t, r))
    expected = py.compounding_apply(py_comp, getattr(py.COMPOUND_TRANSFORM, transform_name), t, v)
    got = compounding_apply(getattr(COMPOUNDING, comp_name), getattr(COMPOUND_TRANSFORM, transform_name), t, v)
    assert got == expected


@pytest.mark.parametrize('comp_name', py.COMPOUNDING.all_names())
@pytest.mark.parametrize('t,r', _TR, ids=[f't={t}-r={r}' for t, r in _TR])
def test_accrual_to_rate_roundtrip(comp_name, t, r):
    comp = getattr(COMPOUNDING, comp_name)
    acc = compounding_apply(comp, COMPOUND_TRANSFORM.RATE_TO_ACCRUAL, t, r)
    got = compounding_apply(comp, COMPOUND_TRANSFORM.ACCRUAL_TO_RATE, t, acc)
    if t == 0:
        assert got == 0.0
    else:
        assert got == pytest.approx(r)
