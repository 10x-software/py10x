"""QuantLib helper dates vs the native deposit and OIS dates, on md dates the dev quotes do not cover."""

from datetime import date
from unittest.mock import patch

import pytest
import QuantLib as ql
from core_10x.trait_method_error import TraitMethodError
from xxcommon.rdate import RDate
from xxfin import ir_zero_rate_curve_ql as zql
from xxfin.ir_cash_deposit_quotable import IRCashDepositQuotable
from xxfin.ir_swap_quotable import IRSwapQuotable
from xxfin.pricing_context import PricingContext
from xxfin.ql_adapter import QL


@pytest.fixture
def eval_date():
    settings = ql.Settings.instance()
    saved = settings.evaluationDate
    yield settings
    settings.evaluationDate = saved


def _basis(md_date: date) -> dict:
    return {**PricingContext.current().md_basis, 'md_date': md_date}


def _ois_helper(q: IRSwapQuotable) -> ql.OISRateHelper:
    mc = q.mkt_conventions
    curve = ql.RelinkableYieldTermStructureHandle(ql.FlatForward(QL.to_date(q.md_date), 0.03, ql.Actual360()))
    return QL.swap_helper(q, mc, QL.overnight_index(mc, curve))


def test_overnight_index_has_no_fixing_lag():
    # A nonzero OvernightIndex fixingDays is a lookback on every fixing, not the swap spot lag.
    mc = IRSwapQuotable(tenor = RDate('5Y'), mkt_name = 'SOFR', **_basis(date(2025, 10, 10))).mkt_conventions
    assert QL.overnight_index(mc, ql.RelinkableYieldTermStructureHandle()).fixingDays() == 0


@pytest.mark.parametrize('md_date, mkt', [
    (date(2024, 3, 26), 'SOFR'),    # spot 3/28 is the last US business day of March: QL's default end-of-month rule kicks in
    (date(2024, 3, 26), 'SONIA'),
    (date(2024, 3, 27), 'CORRA'),
    (date(2024, 3, 28), 'SOFR'),    # Good Friday: spot is T+2 on FD (4/1) but T+1 on US
    (date(2025, 10, 10), 'SOFR'),
])
@pytest.mark.parametrize('tenor', ['2Y', '5Y', '10Y'])
def test_ois_helper_schedule_matches_native(eval_date, md_date, mkt, tenor):
    eval_date.evaluationDate = QL.to_date(md_date)
    q = IRSwapQuotable(tenor = RDate(tenor), mkt_name = mkt, **_basis(md_date))
    q.quote = 0.03     # no dev quotes on most of these dates
    swap = _ois_helper(q).swap()
    for leg in (swap.overnightLeg(), swap.fixedLeg()):
        coupons = [ql.as_coupon(c) for c in leg]
        assert coupons[0].accrualStartDate().to_date() == q.start_date
        assert [c.accrualEndDate().to_date() for c in coupons] == list(q.end_dates)
        assert [c.date().to_date() for c in coupons] == list(q.pay_dates)


@pytest.mark.parametrize('tenor', ['1B', '1W', '3M', '12M'])
def test_deposit_helper_dates_match_native(eval_date, tenor):
    md_date = date(2025, 10, 10)
    eval_date.evaluationDate = QL.to_date(md_date)
    q = IRCashDepositQuotable(tenor = RDate(tenor), mkt_name = 'SOFR', **_basis(md_date))
    h = QL.deposit_helper(q, q.mkt_conventions, md_date)
    assert (h.earliestDate().to_date(), h.maturityDate().to_date()) == (q.start_date, q.end_date)


def test_evaluation_date_restored_when_bootstrap_raises(eval_date):
    marker = ql.Date(2, 2, 2018)
    eval_date.evaluationDate = marker

    def _boom(*args, **kwargs):
        raise RuntimeError('bootstrap')

    with patch.object(zql.ql, 'PiecewiseLinearZero', _boom), pytest.raises(TraitMethodError, match = 'RuntimeError: bootstrap'):
        _ = zql.ZeroRateCurveQL(mkt_name = 'SOFR', **PricingContext.current().md_basis).payload
    assert eval_date.evaluationDate == marker
