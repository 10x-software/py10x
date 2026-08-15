from datetime import date, timedelta

import pytest
from xxcommon.rdate import BIZDAY_ROLL_RULE, RDate
from xxfin.ccy import Ccy
from xxfin.ccy_forward import CcyForward, CcyUnit
from xxfin.fin_calendar import FinCalendar
from xxfin.fx_forward_curve import FXForwardCurveSimple, FXForwardQuotable, FXSpotQuotable
from xxfin.ir_cash_deposit_quotable import IRCashDepositQuotable
from xxfin.ir_swap_quotable import IRSwapQuotable
from xxfin.ir_zero_rate_curve import ZeroRateCurve
from xxfin.pricing_context import PricingContext


class TestFinInstrument:
    def setup_method(self):
        self.pc = PricingContext.current()
        self.md_basis = self.pc.md_basis

        self.usd_cu = CcyUnit.existing_instance(denominated=Ccy('USD'))
        self.gbp_cu = CcyUnit.existing_instance(denominated=Ccy('GBP'))
        self.cad_cu = CcyUnit.existing_instance(denominated=Ccy('CAD'))

        self.usd_cf = CcyForward.existing_instance(denominated=Ccy('USD'), end_date=date(2026, 8, 4))
        self.gbp_cf = CcyForward.existing_instance(denominated=Ccy('GBP'), end_date=date(2026, 8, 4))
        self.cad_cf = CcyForward.existing_instance(denominated=Ccy('CAD'), end_date=date(2026, 8, 4))
        self.cfs = [self.usd_cf, self.gbp_cf, self.cad_cf]

        d6m_us = RDate('6M').apply(self.pc.md_date, FinCalendar('US'), BIZDAY_ROLL_RULE.FOLLOWING)
        d6y_us = RDate('6Y').apply(self.pc.md_date, FinCalendar('US'), BIZDAY_ROLL_RULE.FOLLOWING)
        d2y_gb = RDate('1Y').apply(self.pc.md_date, FinCalendar('GB'), BIZDAY_ROLL_RULE.FOLLOWING)
        d3y_gb = RDate('3Y').apply(self.pc.md_date, FinCalendar('GB'), BIZDAY_ROLL_RULE.FOLLOWING)
        self.usd_cf_6m = CcyForward.existing_instance(denominated=Ccy('USD'), end_date=d6m_us)
        self.usd_cf_6y = CcyForward.existing_instance(denominated=Ccy('USD'), end_date=d6y_us)
        self.gbp_cf_2y = CcyForward.existing_instance(denominated=Ccy('GBP'), end_date=d2y_gb)
        self.gbp_cf_3y = CcyForward.existing_instance(denominated=Ccy('GBP'), end_date=d3y_gb)

        self.gbp_fxc = FXForwardCurveSimple(mkt_name='GBP/USD', **self.md_basis)
        self.cad_fxc = FXForwardCurveSimple(mkt_name='USD/CAD', **self.md_basis)

        self.usd_zrc = ZeroRateCurve(mkt_name='SOFR', **self.md_basis)
        self.gbp_zrc = ZeroRateCurve(mkt_name='SONIA', **self.md_basis)
        self.cad_zrc = ZeroRateCurve(mkt_name='CORRA', **self.md_basis)

        self.sofr_cash_depos = [
            IRCashDepositQuotable.existing_instance(tenor=RDate('1B'), mkt_name='SOFR', **self.md_basis),
            IRCashDepositQuotable.existing_instance(tenor=RDate('1W'), mkt_name='SOFR', **self.md_basis),
            IRCashDepositQuotable.existing_instance(tenor=RDate('1M'), mkt_name='SOFR', **self.md_basis),
            IRCashDepositQuotable.existing_instance(tenor=RDate('3M'), mkt_name='SOFR', **self.md_basis),
            IRCashDepositQuotable.existing_instance(tenor=RDate('6M'), mkt_name='SOFR', **self.md_basis),
            IRCashDepositQuotable.existing_instance(tenor=RDate('9M'), mkt_name='SOFR', **self.md_basis),
            IRCashDepositQuotable.existing_instance(tenor=RDate('12M'), mkt_name='SOFR', **self.md_basis),
        ]
        self.sofr_swaps = [
            IRSwapQuotable.existing_instance(tenor=RDate('5Y'), mkt_name='SOFR', **self.md_basis),
            IRSwapQuotable.existing_instance(tenor=RDate('10Y'), mkt_name='SOFR', **self.md_basis),
            IRSwapQuotable.existing_instance(tenor=RDate('20Y'), mkt_name='SOFR', **self.md_basis),
            IRSwapQuotable.existing_instance(tenor=RDate('30Y'), mkt_name='SOFR', **self.md_basis),
        ]

        self.sonia_cash_depos = [
            IRCashDepositQuotable.existing_instance(tenor=RDate('1B'), mkt_name='SONIA', **self.md_basis),
            IRCashDepositQuotable.existing_instance(tenor=RDate('1W'), mkt_name='SONIA', **self.md_basis),
            IRCashDepositQuotable.existing_instance(tenor=RDate('1M'), mkt_name='SONIA', **self.md_basis),
            IRCashDepositQuotable.existing_instance(tenor=RDate('3M'), mkt_name='SONIA', **self.md_basis),
            IRCashDepositQuotable.existing_instance(tenor=RDate('6M'), mkt_name='SONIA', **self.md_basis),
            IRCashDepositQuotable.existing_instance(tenor=RDate('9M'), mkt_name='SONIA', **self.md_basis),
            IRCashDepositQuotable.existing_instance(tenor=RDate('12M'), mkt_name='SONIA', **self.md_basis),
        ]
        self.sonia_swaps = [
            IRSwapQuotable.existing_instance(tenor=RDate('5Y'),  mkt_name='SONIA', **self.md_basis),
            IRSwapQuotable.existing_instance(tenor=RDate('10Y'), mkt_name='SONIA', **self.md_basis),
            IRSwapQuotable.existing_instance(tenor=RDate('20Y'), mkt_name='SONIA', **self.md_basis),
            IRSwapQuotable.existing_instance(tenor=RDate('30Y'), mkt_name='SONIA', **self.md_basis),
        ]

        self.gbp_fx_spot = FXSpotQuotable(mkt_name='GBP/USD', **self.md_basis)
        self.gbp_fx_fwds = [
            FXForwardQuotable.existing_instance(tenor=RDate('1B'),  mkt_name='GBP/USD', **self.md_basis),
            FXForwardQuotable.existing_instance(tenor=RDate('1W'),  mkt_name='GBP/USD', **self.md_basis),
            FXForwardQuotable.existing_instance(tenor=RDate('1M'),  mkt_name='GBP/USD', **self.md_basis),
            FXForwardQuotable.existing_instance(tenor=RDate('3M'),  mkt_name='GBP/USD', **self.md_basis),
            FXForwardQuotable.existing_instance(tenor=RDate('6M'),  mkt_name='GBP/USD', **self.md_basis),
            FXForwardQuotable.existing_instance(tenor=RDate('9M'),  mkt_name='GBP/USD', **self.md_basis),
            FXForwardQuotable.existing_instance(tenor=RDate('12M'), mkt_name='GBP/USD', **self.md_basis),
            FXForwardQuotable.existing_instance(tenor=RDate('2Y'),  mkt_name='GBP/USD', **self.md_basis),
            FXForwardQuotable.existing_instance(tenor=RDate('5Y'),  mkt_name='GBP/USD', **self.md_basis),
            FXForwardQuotable.existing_instance(tenor=RDate('20Y'), mkt_name='GBP/USD', **self.md_basis),
        ]

        self.cad_fx_spot = FXSpotQuotable(mkt_name='USD/CAD', **self.md_basis)
        self.cad_fx_fwds = [
            FXForwardQuotable.existing_instance(tenor=RDate('1W'),  mkt_name='USD/CAD', **self.md_basis),
            FXForwardQuotable.existing_instance(tenor=RDate('1M'),  mkt_name='USD/CAD', **self.md_basis),
            FXForwardQuotable.existing_instance(tenor=RDate('3M'),  mkt_name='USD/CAD', **self.md_basis),
            FXForwardQuotable.existing_instance(tenor=RDate('6M'),  mkt_name='USD/CAD', **self.md_basis),
            FXForwardQuotable.existing_instance(tenor=RDate('9M'),  mkt_name='USD/CAD', **self.md_basis),
            FXForwardQuotable.existing_instance(tenor=RDate('12M'), mkt_name='USD/CAD', **self.md_basis),
            FXForwardQuotable.existing_instance(tenor=RDate('2Y'),  mkt_name='USD/CAD', **self.md_basis),
            FXForwardQuotable.existing_instance(tenor=RDate('5Y'),  mkt_name='USD/CAD', **self.md_basis),
        ]

        self.some_dates = [
            date(2028, 1, 1),
            date(2029, 1, 1),
            date(2039, 1, 1),
            date(2049, 1, 1),
        ]

    def test_denominated_choices(self):
        all_ccys = {ccy.name: ccy for ccy in Ccy.load_many()}
        assert self.usd_cu.denominated_choices() == all_ccys
        assert self.gbp_cf.denominated_choices() == all_ccys

    def test_price_ccy(self):
        gbp_fx_now = self.gbp_fxc.now_rate
        assert self.usd_cu.price_ccy(Ccy('GBP')) == pytest.approx(1.0 / gbp_fx_now, abs=1e-15)
        assert self.usd_cf.price_ccy(Ccy('GBP')) == pytest.approx(self.usd_cf.price / gbp_fx_now, abs=1e-15)

        cad_fx_now = self.cad_fxc.now_rate
        assert self.usd_cu.price_ccy(Ccy('CAD')) == pytest.approx(cad_fx_now, abs=1e-15)
        assert self.usd_cf.price_ccy(Ccy('CAD')) == pytest.approx(self.usd_cf.price * cad_fx_now, abs=1e-15)

        assert self.cad_cu.price_ccy(Ccy('GBP')) == pytest.approx(1.0 / cad_fx_now / gbp_fx_now, abs=1e-15)
        assert self.cad_cu.price_ccy(Ccy('GBP')) == pytest.approx(self.cad_cu.price / cad_fx_now / gbp_fx_now, abs=1e-15)

    def test_disc_curve(self):
        assert self.usd_cf.disc_curve == self.usd_zrc
        assert self.gbp_cf.disc_curve == self.gbp_zrc
        assert self.cad_cf.disc_curve == self.cad_zrc

    def test_mkt_deps_for_discounting(self):
        mkt_deps_cases = [
            ((self.usd_cf_6m, self.usd_cf_6y), (self.sofr_cash_depos, self.sofr_swaps)),
            ((self.gbp_cf_2y, self.gbp_cf_3y), (self.sonia_cash_depos, self.sonia_swaps)),
        ]

        for mdc in mkt_deps_cases:
            secs = mdc[0]
            cash_depos, swaps = mdc[1]
            for cf in secs:
                ed = cf.max_date()
                cds = []
                for cd in cash_depos:
                    cds.append(cd)
                    if cd.pay_date > ed:
                        break

                swps = []
                if ed > cd.pay_date:  ## cf.max_date > last cd.pay_date (=max(cd.pay_date) for all cds)
                    for swp in swaps:
                        swps.append(swp)
                        if swp.pay_date > ed:
                            break

                deps = {}
                if cds:
                    deps[IRCashDepositQuotable] = cds
                if swps:
                    deps[IRSwapQuotable] = swps
                assert deps == cf.mkt_deps_for_discounting

    def test_mkt_deps_for_ccy(self):
        mkt_fx_deps_cases = [
            ((self.usd_cf_6m, self.usd_cf_6y), (('GBP', self.gbp_fx_spot, self.gbp_fx_fwds),)),
            ((self.gbp_cf_2y, self.gbp_cf_3y,), (('GBP', self.gbp_fx_spot, self.gbp_fx_fwds), ('CAD', self.cad_fx_spot, self.cad_fx_fwds))),   ## GBP/CAD resolves into GBP/USD and USD/CAD dollar crosses
        ]

        for mdc in mkt_fx_deps_cases:
            secs = mdc[0]
            ccys = mdc[1]

            for cf in secs:
                fxdeps = {FXForwardQuotable: [], FXSpotQuotable: []}

                ed = cf.max_date()

                for ccy_name,ccy_fx_spot, ccy_fx_fwds in ccys:
                    fxdeps[FXSpotQuotable].append(ccy_fx_spot)

                    for fxf in ccy_fx_fwds:
                        fxf_ed = fxf.end_date
                        fxdeps[FXForwardQuotable].append(fxf)
                        if fxf_ed > ed:
                            break

                calc_fxdeps = cf.mkt_deps_for_ccy(Ccy(ccy_name))
                assert fxdeps == calc_fxdeps ##this ccy_name is the "last" in the list

    def test_discount_factor(self):
        old_d = self.pc.md_date - timedelta(days=365)
        for cf, zrc in zip(
            [self.usd_cf, self.gbp_cf, self.cad_cf],
            [self.usd_zrc.payload, self.gbp_zrc.payload, self.cad_zrc.payload],
            strict=True,
        ):
            assert cf.discount_factor(old_d) == 1.0
            for d in self.some_dates:
                assert cf.discount_factor(d) == zrc.discount_factor(d)
