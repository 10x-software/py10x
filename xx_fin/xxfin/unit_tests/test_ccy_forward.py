from datetime import date

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

        usd_zrc_obj = ZeroRateCurve(
            mkt_name        = 'SOFR',
            provider_name   = self.pc.mkt_data_provider_name,
            md_date         = self.today,
            snapshot        = self.pc.snapshot,
        )
        self.usd_zrc = usd_zrc_obj.payload

        gbp_zrc_obj = ZeroRateCurve(
            mkt_name        = 'SONIA',
            provider_name   = self.pc.mkt_data_provider_name,
            md_date         = self.today,
            snapshot        = self.pc.snapshot,
        )
        self.gbp_zrc = gbp_zrc_obj.payload

    def test_price(self):
        for d, ufwd, gfwd in zip(self.days, self.usd_fwds, self.gbp_fwds, strict=True):
            assert ufwd.price == self.usd_zrc.discount_factor(d, self.today)
            assert gfwd.price == self.gbp_zrc.discount_factor(d, self.today)

    def test_mkt_deps(self):
        for cf in self.fwds:
            assert cf.mkt_deps == cf.mkt_deps_for_discounting

    def test_mkt_deps_deps_for_discounting(self):
        ...

    def test_max_date(self):
        for d, ufwd, gfwd in zip(self.days, self.usd_fwds, self.gbp_fwds, strict=True):
            assert ufwd.max_date() == d
            assert gfwd.max_date() == d