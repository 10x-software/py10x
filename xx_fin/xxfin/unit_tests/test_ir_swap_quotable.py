from datetime import date, timedelta

import pytest
from xxcommon.rdate import BIZDAY_ROLL_RULE, RDate
from xxfin.py_day_count_convention import DAY_COUNT_CONVENTION
from xxfin.fin_calendar import FinCalendar
from xxfin.ir_rate_mkt_conventions import IRRateMktConventions
from xxfin.ir_swap_quotable import IRSwapQuotable
from xxfin.ir_zero_rate_curve import ZeroRateCurve
from xxfin.pricing_context import PricingContext

class TestIRSwapQuotable:
    def setup_method(self):
        self.pc = PricingContext.current()
        self.md_basis = self.pc.md_basis

        self.sofr = dict(
            irate       = 'SOFR',
            cal         = FinCalendar('US'),
            roll_rule   = BIZDAY_ROLL_RULE.MOD_FOLLOWING,
            dc_conv     = DAY_COUNT_CONVENTION.ACT360,
            swap_freq   = RDate('1Y'),
            pay_delay   = RDate('2B'),
            tenor_sym   = '5Y',
        )

        self.sonia = dict(
            irate       = 'SONIA',
            cal         = FinCalendar('GB'),
            roll_rule   = BIZDAY_ROLL_RULE.MOD_FOLLOWING,
            dc_conv     = DAY_COUNT_CONVENTION.ACT365,
            swap_freq   = RDate('1Y'),
            pay_delay   = RDate('2B'),
            tenor_sym   = '10Y',
            # tenor_sym   = '5Y',
        )

        self.irates = [self.sofr, self.sonia]
        # for irate in self.irates:
        #     irate['tenor'] = RDate(self.sofr['tenor_sym'])
        #     irate['mc'] = IRRateMktConventions(mkt_name=self.sofr['irate'])
        #     irate['zrc'] = ZeroRateCurve(mkt_name=self.sofr['irate'], **self.md_basis).payload
        #     irate['sq'] = IRSwapQuotable(mkt_name=self.sofr['irate'], tenor=self.sofr['tenor'], **self.md_basis)

        self.sofr['tenor']  = RDate(self.sofr['tenor_sym'])
        self.sofr['mc']     = IRRateMktConventions(mkt_name = self.sofr['irate'])
        self.sofr['zrc']    = ZeroRateCurve(       mkt_name = self.sofr['irate'], **self.md_basis).payload
        self.sofr['sq']     = IRSwapQuotable(      mkt_name = self.sofr['irate'], tenor = self.sofr['tenor'], **self.md_basis)

    def test_start_end_dates(self):
        swap_start_date = self.sofr['mc'].spot_date(self.md_basis['md_date'])
        swap_end_date = self.sofr['tenor'].apply(swap_start_date, self.sofr['cal'], self.sofr['roll_rule'])

        assert swap_start_date == self.sofr['sq'].start_date
        assert swap_end_date   == self.sofr['sq'].end_date

    def test_start_dates(self):
        swap = self.sofr['sq']
        start_dates = [swap.start_date] + swap.end_dates[:-1]
        assert start_dates == swap.start_dates

    def test_end_dates(self):
        swap_freq = self.sofr['swap_freq']
        cal       = self.sofr['cal']
        roll_rule = self.sofr['roll_rule']
        swap      = self.sofr['sq']

        end_dates = []
        non_rolled_ed = rolled_ed = swap.start_date
        while rolled_ed < swap.end_date:
            non_rolled_ed = swap_freq.apply_no_roll(non_rolled_ed)
            rolled_ed = RDate.roll_to_bizday(non_rolled_ed, cal, roll_rule)
            end_dates.append(rolled_ed)

        assert end_dates == swap.end_dates

    def test_pay_dates(self):
        cal       = self.sofr['cal']
        roll_rule = self.sofr['roll_rule']
        pay_delay = self.sofr['pay_delay']
        swap      = self.sofr['sq']

        pay_dates   = [ pay_delay.apply(ed, cal, roll_rule) for ed in swap.end_dates ]
        assert pay_dates == swap.pay_dates

    def test_incremental_dc_fractions(self):
        swap = self.sofr['sq']
        incr_dcfs = [self.sofr['dc_conv'](sd, ed) for sd, ed in zip(swap.start_dates, swap.end_dates, strict=True)]
        assert incr_dcfs == swap.incremental_dc_fractions

    def test_anuity_calc(self):
        zrc = self.sofr['zrc']
        swap = self.sofr['sq']
        num_periods = len(swap.pay_dates)
        assert swap.annuity_calc(zrc) == swap.annuity_calc(zrc, num_periods), f'annuity default num periods is off'

        for num in range(num_periods):
            manual_ann = sum(dcf * df for dcf, df in zip(swap.incremental_dc_fractions[:num + 1],
                                                         zrc.discount_factors(swap.pay_dates, today=self.md_basis['md_date'])[:num + 1]))
            assert manual_ann == swap.annuity_calc(zrc, num + 1)
