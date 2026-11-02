"""QuantLib helper dates vs the native deposit and OIS dates, on md dates the dev quotes do not cover."""

from datetime import date

import pytest
import QuantLib as ql
from xxcommon.rdate import RDate
from xxfin.ir_cash_deposit_quotable import IRCashDepositQuotable
from xxfin.ir_swap_quotable import IRSwapQuotable
from xxfin.ir_zero_rate_curve_ql import ZeroRateCurveQL
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
@pytest.mark.parametrize('tenor', ['18M', '2Y', '5Y', '10Y'])     # 18M: a front stub on the backward schedule
def test_ois_helper_schedule_matches_native(eval_date, md_date, mkt, tenor):
    eval_date.evaluationDate = QL.to_date(md_date)
    q = IRSwapQuotable(tenor = RDate(tenor), mkt_name = mkt, **_basis(md_date))
    q.quote = 0.03     # no dev quotes on most of these dates
    swap = _ois_helper(q).swap()
    legs = ((swap.overnightLeg(), q.end_dates, q.pay_dates), (swap.fixedLeg(), q.fixed_end_dates, q.fixed_pay_dates))
    for leg, end_dates, pay_dates in legs:
        coupons = [ql.as_coupon(c) for c in leg]
        assert coupons[0].accrualStartDate().to_date() == q.start_date
        assert [c.accrualEndDate().to_date() for c in coupons] == list(end_dates)
        assert [c.date().to_date() for c in coupons] == list(pay_dates)


@pytest.mark.parametrize('md_date, tenor', [
    *((date(2025, 10, 10), t) for t in ('1B', '1W', '3M', '12M')),
    (date(2024, 4, 16), '12M'),     # ends Good Friday 2025: an FD business day, a US holiday
])
def test_deposit_helper_dates_match_native(eval_date, md_date, tenor):
    eval_date.evaluationDate = QL.to_date(md_date)
    q = IRCashDepositQuotable(tenor = RDate(tenor), mkt_name = 'SOFR', **_basis(md_date))
    q.quote = 0.03
    h = QL.deposit_helper(q, q.mkt_conventions, md_date)
    assert (h.earliestDate().to_date(), h.maturityDate().to_date()) == (q.start_date, q.end_date)


def test_bootstrap_leaves_evaluation_date_alone(eval_date):
    marker = ql.Date(2, 2, 2018)
    eval_date.evaluationDate = marker
    curve = ZeroRateCurveQL(mkt_name = 'SOFR', **PricingContext.current().md_basis).payload
    assert list(curve.dates)
    assert eval_date.evaluationDate == marker
