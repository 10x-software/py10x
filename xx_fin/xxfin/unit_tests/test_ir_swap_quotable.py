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
        )

        self.irates = [self.sofr, self.sonia]
        for irate in self.irates:
            irate['tenor']  = RDate(irate['tenor_sym'])
            irate['mc']     = IRRateMktConventions(mkt_name = irate['irate'])
            irate['zrc']    = ZeroRateCurve(mkt_name = irate['irate'], **self.md_basis).payload
            irate['sq']     = IRSwapQuotable(mkt_name = irate['irate'], tenor=irate['tenor'], **self.md_basis)

    def test_start_end_dates(self):
        for irate in self.irates:
            swap_start_date = irate['mc'].spot_date(self.md_basis['md_date'])
            swap_end_date = irate['tenor'].apply(swap_start_date, irate['cal'], irate['roll_rule'])

            assert swap_start_date == irate['sq'].start_date
            assert swap_end_date   == irate['sq'].end_date

    def test_start_dates(self):
        for irate in self.irates:
            swap = irate['sq']
            assert [swap.start_date] + swap.end_dates[:-1] == swap.start_dates

    def test_end_dates(self):
        for irate in self.irates:
            swap_freq = irate['swap_freq']
            cal       = irate['cal']
            roll_rule = irate['roll_rule']
            swap      = irate['sq']

            end_dates = []
            non_rolled_ed = rolled_ed = swap.start_date
            while rolled_ed < swap.end_date:
                non_rolled_ed = swap_freq.apply_no_roll(non_rolled_ed)
                rolled_ed = RDate.roll_to_bizday(non_rolled_ed, cal, roll_rule)
                end_dates.append(rolled_ed)

            assert end_dates == swap.end_dates

    def test_pay_dates(self):
        for irate in self.irates:
            cal       = irate['cal']
            roll_rule = irate['roll_rule']
            pay_delay = irate['pay_delay']
            swap      = irate['sq']
            assert [ pay_delay.apply(ed, cal, roll_rule) for ed in swap.end_dates ] == swap.pay_dates

    def test_incremental_dc_fractions(self):
        for irate in self.irates:
            swap = irate['sq']
            incr_dcfs = [irate['dc_conv'](sd, ed) for sd, ed in zip(swap.start_dates, swap.end_dates, strict=True)]
            assert incr_dcfs == swap.incremental_dc_fractions

    def test_anuity_calc(self):
        for irate in self.irates:
            zrc = irate['zrc']
            swap = irate['sq']
            num_periods = len(swap.pay_dates)
            assert swap.annuity_calc(zrc) == swap.annuity_calc(zrc, num_periods), f'annuity default num periods is off'

            for num in range(num_periods):
                manual_ann = sum(dcf * df for dcf, df in zip(swap.incremental_dc_fractions[:num + 1],
                                                             zrc.discount_factors(swap.pay_dates, today=self.md_basis['md_date'])[:num + 1]))
                assert manual_ann == swap.annuity_calc(zrc, num + 1)

    def test_periods(self):
        for irate in self.irates:
            swap = irate['sq']
            periods = [(sd, ed, pd, dcf) for sd, ed, pd, dcf in zip( swap.start_dates, swap.end_dates, swap.pay_dates, swap.incremental_dc_fractions, strict=True)]
            assert periods == swap.periods()

    def test_empty_swap(self):
        sq = IRSwapQuotable(mkt_name='SONIA', tenor=RDate('0C'), **self.md_basis)
        assert sq.start_dates == sq.end_dates == sq.pay_dates == sq.periods() == sq.incremental_dc_fractions  == []