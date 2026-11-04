from datetime import date

import pytest
from xxfin.ccy_forward import Ccy, CcyForward, PricingContext
from xxfin.ir_zero_rate_curve import ZeroRateCurve


class TestCcyForward:
    def setup_method(self):
        chday = date(2026, 12, 25 )
        nyday = date(2026, 12, 31 )
        inday = date(2026, 7, 4 )
        day   = date(2026, 7, 30 )
        self.days = [chday, nyday, inday, day]

        self.usd_chd = CcyForward.existing_instance(denominated = Ccy('USD'),end_date = chday)
        self.usd_nyd = CcyForward.existing_instance(denominated = Ccy('USD'),end_date = nyday)
        self.usd_ind = CcyForward.existing_instance(denominated = Ccy('USD'),end_date = inday)
        self.usd_d   = CcyForward.existing_instance(denominated = Ccy('USD'),end_date = day)
        self.usd_fwds= [self.usd_chd, self.usd_nyd, self.usd_ind, self.usd_d]

        self.gbp_chd = CcyForward.existing_instance(denominated = Ccy('GBP'),end_date = chday)
        self.gbp_nyd = CcyForward.existing_instance(denominated = Ccy('GBP'),end_date = nyday)
        self.gbp_ind = CcyForward.existing_instance(denominated = Ccy('GBP'),end_date = inday)
        self.gbp_d   = CcyForward.existing_instance(denominated = Ccy('GBP'),end_date = day)
        self.gbp_fwds= [self.gbp_chd, self.gbp_nyd, self.gbp_ind, self.gbp_d]

        self.fwds    = self.usd_fwds + self.gbp_fwds

        self.pc  = PricingContext.current()
        self.today = self.pc.md_date

        self.usd_zrc = ZeroRateCurve(
            mkt_name        = 'SOFR',
            provider_name   = self.pc.mkt_data_provider_name,
            md_date         = self.today,
            snapshot        = self.pc.snapshot,
        )

        self.gbp_zrc = ZeroRateCurve(
            mkt_name        = 'SONIA',
            provider_name   = self.pc.mkt_data_provider_name,
            md_date         = self.today,
            snapshot        = self.pc.snapshot,
        )

    @pytest.mark.usefixtures('cxx_or_py_zero_rate_curve')
    def test_price(self):
        for d, ufwd, gfwd in zip(self.days, self.usd_fwds, self.gbp_fwds, strict=True):
            assert ufwd.price == self.usd_zrc.payload.discount_factor(d, self.today)
            assert gfwd.price == self.gbp_zrc.payload.discount_factor(d, self.today)

    @pytest.mark.usefixtures('cxx_or_py_zero_rate_curve')
    def test_price_to_pricing_date(self):
        pd = date(2026, 7, 10)      ## after inday, before the others
        self.pc.pricing_date = pd
        for d, usf, gbf in zip(self.days, self.usd_fwds, self.gbp_fwds, strict=True):
            for fwd, zrc in ((usf, self.usd_zrc), (gbf, self.gbp_zrc)):
                if d <= pd:
                    assert fwd.price == 1.
                    continue
                ## riding the md_date curve: DF(md_date, d) / DF(md_date, pd)
                rc = zrc.payload
                assert fwd.price == pytest.approx(rc.discount_factor(d, self.today) / rc.discount_factor(pd, self.today), rel=1e-15)
                assert fwd.price != rc.discount_factor(d, self.today)     ## pd matters (the dev data has negative rates too, so no sign check)

    def test_pricing_date(self):
        assert self.pc.pricing_date == self.today
        with pytest.raises(Exception, match='must not be before md_date'):
            self.pc.pricing_date = date(2025, 10, 9)

    ## TODO: retired along with FinInstrument.mkt_deps_for_discounting (see mkt_deps_design_notes.md).
    ##       OK to discard these tests outright instead of keeping them commented?
    # def test_mkt_deps(self):
    #     for cf in self.fwds:
    #         assert cf.mkt_deps == cf.mkt_deps_for_discounting
    #
    # def test_mkt_deps_deps_for_discounting(self):
    #     ...

    def test_max_date(self):
        for d, ufwd, gfwd in zip(self.days, self.usd_fwds, self.gbp_fwds, strict=True):
            assert ufwd.max_date() == d
            assert gfwd.max_date() == d