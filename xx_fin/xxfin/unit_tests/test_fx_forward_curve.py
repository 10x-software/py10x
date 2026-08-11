import pytest
from core_10x.trait_method_error import TraitMethodError
# from xxcommon.py_curve import IP_KIND, Curve, DateCurve
from xxcommon.rdate import RDate, date
from xxfin.fx_forward_curve import FXForwardCurve, FXForwardCurveSimple
from xxfin.fx_forward_curve_mas import FxForwardCurveMas
from xxfin.fx_mkt_conventions import FXMktConventions
from xxfin.fx_spot_fwd_quotable import FXForwardQuotable, FXSpotQuotable
from xxfin.pricing_context import PricingContext


def quotes(crosses, md_basis):
    provider = md_basis['provider_name']
    md_date  = md_basis['md_date']
    snapshot = md_basis['snapshot']

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
                r = FXForwardQuotable(mkt_name=cross, tenor=rd, provider_name=provider, md_date=md_date, snapshot=snapshot).quote
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
        self.md_basis = PricingContext.current().md_basis
        self.crosses = [ 'USD/CAD', 'GBP/USD', 'EUR/USD', 'USD/CHF']


    def test_FxForwardCurveSimple(self):
        for cross, (dates, rates) in quotes(self.crosses, self.md_basis).items():
            fxc_object = FXForwardCurveSimple(mkt_name = cross, **self.md_basis)
            fxc = fxc_object.payload
            for d, r in zip(dates, rates, strict=True):
                calc = fxc.value(d)
                assert r == pytest.approx(calc)

    def test_FxForwardCurveSimple_spot_only_flat_curve(self):
        some_dates = [
            date(2028, 1, 1),
            date(2029, 1, 1),
            date(2039, 1, 1),
            date(2049, 1, 1),
        ]
        for cross in self.crosses:
            fxc_object = FXForwardCurveSimple(mkt_name = cross, **self.md_basis)
            fxc_object.mkt_assembly_object.quotable_stubs_by_class.pop(FXForwardQuotable)
            spot_rate = FXSpotQuotable(mkt_name = cross, **self.md_basis).quote
            fxc = fxc_object.payload
            ## TODO: what's replaces CurveParams in cxx?
            # assert fxc.params == CurveParams(ip_kind = IP_KIND.ZERO)

            for d in some_dates:
                assert fxc.value(d) == pytest.approx(spot_rate)

    def test_FxForwardCurveSimple_missing_spot(self):
        cross = 'USD/CAD'
        fxc_object = FXForwardCurveSimple(mkt_name = cross, **self.md_basis)
        fxc_object.mkt_assembly_object.quotable_stubs_by_class.pop(FXSpotQuotable)
        with pytest.raises(TraitMethodError, match='Spot FX rate quote must be present to build an FX forward curve for USD/CAD'):
            _ = fxc_object.payload

    def test_FxForwardCurveSimple_spot_ON_conflict(self):
        cross = 'USD/CAD'
        fxc_object = FXForwardCurveSimple(mkt_name = cross, **self.md_basis)
        mao = fxc_object.mkt_assembly_object.quotable_stubs_by_class
        mao[FXForwardQuotable] = '1B, ' + mao[FXForwardQuotable]

        spot_data_definition = fxc_object.mkt_assembly_object.quotable_stubs_by_class.get(FXSpotQuotable)
        assert spot_data_definition

        with pytest.raises(TraitMethodError, match='USD/CAD >>> 1B <<< forward specification conflicts with spot rate'):
            _ = fxc_object.payload

    def test_FxForwardCurve(self):
        for cross, (dates, rates) in quotes(self.crosses, self.md_basis).items():
            fxc_object = FXForwardCurve(mkt_name = cross, **self.md_basis)
            fxc = fxc_object.payload
            for d, r in zip(dates, rates, strict=True):
                calc = fxc.value(d)
                assert r == pytest.approx(calc)
