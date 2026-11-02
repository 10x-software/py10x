import pytest

from xxfin import cxx_zrc_bootstrap, ir_zero_rate_curve, py_zrc_bootstrap
from xxfin.ir_zero_rate_curve import ZeroRateCurve
from xxfin.pricing_context import PricingContext


def _bootstrap(zrc: ZeroRateCurve, bootstrap_module, monkeypatch, swaps_only: bool) -> list:
    """
    Re-runs ZeroRateCurve.payload_get() with the given bootstrap module, so the py and cxx versions
    see the same quotables and market conventions (the real calendars, roll rules and pay delays)
    """
    from xxfin.rate_curve import RateCurve

    monkeypatch.setattr(ir_zero_rate_curve, 'solve_cash_deposit', bootstrap_module.solve_cash_deposit)
    monkeypatch.setattr(ir_zero_rate_curve, 'solve_swap',         bootstrap_module.solve_swap)

    mc = zrc.mkt_conventions
    res = RateCurve(beginning_of_time = zrc.md_date, quoting_dc_convention = mc.dc_convention, quoting_compounding = mc.compounding)
    if not swaps_only:
        zrc.process_cash_deposits(res)
    zrc.process_swaps(res)
    return res.dates_values()


@pytest.mark.parametrize('mkt_name', ['SOFR', 'SONIA'])
@pytest.mark.parametrize('swaps_only', [False, True], ids=['deposits_and_swaps', 'swaps_only'])
def test_zero_rate_curve_cxx_vs_py(use_cxx, cxx_or_py_rates_curve, monkeypatch, mkt_name, swaps_only):
    if not use_cxx:
        pytest.skip('compares the cxx bootstrap to py on the same (cxx) curve class')

    zrc = ZeroRateCurve(mkt_name = mkt_name, **PricingContext.current().md_basis)

    py_dates_values  = _bootstrap(zrc, py_zrc_bootstrap,  monkeypatch, swaps_only)
    cxx_dates_values = _bootstrap(zrc, cxx_zrc_bootstrap, monkeypatch, swaps_only)

    assert len(py_dates_values) > 2
    assert [d for d, _ in cxx_dates_values] == [d for d, _ in py_dates_values]
    for (d, cxx_v), (_, py_v) in zip(cxx_dates_values, py_dates_values, strict=True):
        assert cxx_v == pytest.approx(py_v, abs = 1.e-12), d


@pytest.mark.parametrize('mkt_name', ['SOFR', 'SONIA'])
def test_zero_rate_curve_vs_quantlib(mkt_name):
    from xxfin.ir_zero_rate_curve_ql import ZeroRateCurveQL

    md_basis = PricingContext.current().md_basis
    native = ZeroRateCurve(  mkt_name = mkt_name, **md_basis).payload
    ql     = ZeroRateCurveQL(mkt_name = mkt_name, **md_basis).payload

    #-- the same pillars: deposits' end dates and swaps' last pay dates
    assert native.dates == ql.dates
    for d, v in native.dates_values():
        assert ql.value(d) == pytest.approx(v, abs = 1.e-10), d
