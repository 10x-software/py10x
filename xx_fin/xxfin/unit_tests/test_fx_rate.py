from datetime import date

import pytest
from xxcommon.rdate import RDate

from xxfin.ccy_cross import CcyCross
from xxfin.fx_forward_curve_mas import FxForwardCurveMas
from xxfin.fx_mkt_conventions import FXMktConventions
from xxfin.fx_rate import FxRate
from xxfin.fx_spot_fwd_quotable import FXForwardQuotable, FXSpotQuotable
from xxfin.pricing_context import PricingContext

crosses   = [ 'GBP/USD', 'EUR/USD', 'USD/JPY']


def quotes(crosses, provider, md_date, snapshot):
    fxmas = FxForwardCurveMas.s_data_per_market

    SPOT = True
    FWDS = True

    quotes = {}
    for cross in crosses:
        mc = FXMktConventions.existing_instance(mkt_name=cross)
        spot = mc.spot_date(md_date)
        cal = mc.calendar
        roll = mc.roll_rule

        dates = []
        rates = []
        if SPOT:
            spotrate = FXSpotQuotable(mkt_name=cross, provider_name=provider, md_date=md_date, snapshot=snapshot).quote
            dates.append(spot)
            rates.append(spotrate)

        if FWDS:
            rdates = [RDate(r.strip()) for r in fxmas[cross][FXForwardQuotable].split(',')]
            for rd in rdates:
                d = rd.apply(spot, cal, roll) if rd.symbol() != '1B' else rd.apply(md_date, cal, roll)
                dates.append(d)
                r = FXForwardQuotable(mkt_name=cross, tenor=rd, provider_name=provider, md_date=md_date,
                                      snapshot=snapshot).quote
                rates.append(r)
            if SPOT:
                rdates.insert(0, 'spot')

        quotes[cross] = (dates, rates)

    return quotes


class TestFxRate:
    @classmethod
    def setup_class(cls):
        # -- moved here from module level: PricingContext.current() must not run at collection
        # time, since pytest imports test modules before the conftest fixture that sets up the
        # store has had a chance to run.
        pc = PricingContext.current()
        cls.provider = pc.mkt_data_provider_name
        cls.md_date  = pc.md_date
        cls.snapshot = pc.snapshot

    def test_quoted_cross_rate(self):
        for cross, (dates, rates) in quotes(crosses, self.provider, self.md_date, self.snapshot).items():
            for d, r in zip(dates, rates, strict=False):
                calc = FxRate.quoted_cross_rate(CcyCross.existing_instance(cross = cross), d, self.provider, self.md_date, self.snapshot)
                assert r == pytest.approx(calc)

    def test_rate_q(self):
        for cross, (dates, rates) in quotes(crosses, self.provider, self.md_date, self.snapshot).items():
            fxr_obj = FxRate(cross_name=cross)

            for d, r in zip(dates, rates, strict=False):
                calc = fxr_obj.rate(d)
                assert r == pytest.approx(calc)

    def test_rate_non_q(self):
        d = date(2030,1,1)
        split = [
            {
                'crs': 'EUR/GBP',
                'top': 'EUR/USD',
                'btm': 'GBP/USD',
                't':    1,
                'b':    1,
            },
            {
                'crs': 'GBP/CAD',
                'top': 'GBP/USD',
                'btm': 'USD/CAD',
                't':    1,
                'b':    -1,
            },
            {
                'crs': 'JPY/CAD',
                'top': 'USD/JPY',
                'btm': 'USD/CAD',
                't':    -1,
                'b':    -1,
            },
            {
                'crs': 'JPY/GBP',
                'top': 'USD/JPY',
                'btm': 'GBP/USD',
                't':    -1,
                'b':    1,
            }

        ]
        for sp in split:
            rc = FxRate(cross_name = sp['crs']).rate(d)
            rt = FxRate(cross_name = sp['top']).rate(d)
            rb = FxRate(cross_name = sp['btm']).rate(d)
            t  = sp['t']
            b  = sp['b']
            assert rc == pytest.approx(rt**t/rb**b)

    def test_rate_same_ccy_cross_good(self):
        d = date(2030,1,1)
        same_ccy_good = ['USD/USD', 'GBP/GBP']
        for c in same_ccy_good:
            r = FxRate(cross_name = c).rate(d)
            assert r == 1

    def test_rate_same_ccy_cross_bad(self):
        d = date(2030, 1, 1)
        same_ccy_bad = ['XXX/XXX', 'AED/AED']
        for c in same_ccy_bad:
            with pytest.raises(ValueError):
                FxRate(cross_name = c).rate(d)
