import pytest
from xxcommon.rdate import RDate

from xxfin.fx_forward_curve import FXForwardCurve, FXForwardCurveSimple
from xxfin.fx_forward_curve_mas import FxForwardCurveMas
from xxfin.fx_mkt_conventions import FXMktConventions
from xxfin.fx_spot_fwd_quotable import FXForwardQuotable, FXSpotQuotable
from xxfin.pricing_context import PricingContext

crosses = ['GBP/USD', 'USD/CAD']


def quotes(crosses, provider, md_date, snapshot):
    fxmas = FxForwardCurveMas.s_data_per_market

    SPOT = True
    FWDS = False

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


class TestFxForwardCurve:
    def setup_method(self):
        # -- moved here from module level: PricingContext.current() must not run at collection
        # time, since pytest imports test modules before the conftest fixture that sets up the
        # store has had a chance to run.
        pc = PricingContext.current()
        self.provider = pc.mkt_data_provider_name
        self.md_date  = pc.md_date
        self.snapshot = pc.snapshot

    def test_FxForwardCurveSimple(self):
        for cross, (dates, rates) in quotes(crosses, self.provider, self.md_date, self.snapshot).items():
            fxc_object = FXForwardCurveSimple(
                provider_name=self.provider,
                md_date=self.md_date,
                snapshot=self.snapshot,
                mkt_name = cross
            )
            fxc = fxc_object.payload
            for d, r in zip(dates, rates, strict=True):
                calc = fxc.value(d)
                assert r == pytest.approx(calc)

    def test_FxForwardCurve(self):
        for cross, (dates, rates) in quotes(crosses, self.provider, self.md_date, self.snapshot).items():
            fxc_object = FXForwardCurve(
                provider_name=self.provider,
                md_date=self.md_date,
                snapshot=self.snapshot,
                mkt_name = cross
            )
            fxc = fxc_object.payload
            for d, r in zip(dates, rates, strict=True):
                calc = fxc.value(d)
                assert r == pytest.approx(calc)