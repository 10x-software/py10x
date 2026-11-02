from datetime import date, timedelta

import pytest
from xxcommon.rdate import BIZDAY_ROLL_RULE, PROPAGATE_DATES, RDate
from xxfin.fin_calendar import FinCalendar
from xxfin.ir_rate_mkt_conventions import IRRateMktConventions
from xxfin.ir_swap_quotable import IRSwapQuotable
from xxfin.ir_zero_rate_curve import ZeroRateCurve
from xxfin.pricing_context import PricingContext
from xxfin.py_day_count_convention import DAY_COUNT_CONVENTION


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
            irate['zrc']    = ZeroRateCurve(mkt_name = irate['irate'], **self.md_basis)
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
            assert [swap.start_date, *swap.end_dates[:-1]] == swap.start_dates

    def test_end_dates(self):
        for irate in self.irates:
            swap_freq = irate['swap_freq']
            cal       = irate['cal']
            roll_rule = irate['roll_rule']
            swap      = irate['sq']

            #-- BACKWARD: each period end is n periods back from the unadjusted swap end (not chained from the next period end)
            unadjusted_end = irate['tenor'].apply_no_roll(swap.start_date)
            end_dates = []
            non_rolled_ed = unadjusted_end
            num_periods = 0
            while non_rolled_ed > swap.start_date:
                end_dates.insert(0, RDate.roll_to_bizday(non_rolled_ed, cal, roll_rule))
                num_periods += 1
                non_rolled_ed = RDate(freq = swap_freq.freq, count = -num_periods).apply_no_roll(unadjusted_end)

            assert non_rolled_ed == swap.start_date, 'a standard swap has no stub'
            assert end_dates == swap.end_dates
            assert end_dates[-1] == swap.end_date

            #-- w/o a stub, FORWARD (n periods from the start date) gives the same schedule
            forward_end_dates = [
                RDate.roll_to_bizday(RDate(freq = swap_freq.freq, count = n).apply_no_roll(swap.start_date), cal, roll_rule)
                for n in range(1, num_periods + 1)
            ]
            assert forward_end_dates == swap.end_dates

    def test_stub_end_dates(self):
        sofr = self.sofr
        cal       = sofr['cal']
        roll_rule = sofr['roll_rule']
        swap = IRSwapQuotable(mkt_name = sofr['irate'], tenor = RDate('18M'), **self.md_basis)

        #-- BACKWARD with a front stub, so the 18M annual swap's periods are 6M + 1Y
        start_date = swap.start_date
        assert swap.end_dates == [
            RDate('6M').apply(start_date, cal, roll_rule),
            RDate('18M').apply(start_date, cal, roll_rule),
        ]
        assert swap.end_dates[-1] == swap.end_date
        assert swap.start_dates == [start_date, swap.end_dates[0]]

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

    def test_fixed_leg(self):
        for irate in self.irates:
            mc   = irate['mc']
            swap = irate['sq']
            fixed_freq = RDate(freq = mc.fixed_leg_swap_tenor_frequency, count = 1)
            starts, ends, _ = fixed_freq.period_dates_for_tenor(swap.start_date, irate['tenor'], irate['cal'], irate['roll_rule'], PROPAGATE_DATES.BACKWARD)

            assert swap.fixed_start_dates == starts
            assert swap.fixed_end_dates   == ends
            assert swap.fixed_pay_dates   == [mc.pay_date(ed) for ed in ends]
            assert swap.fixed_dc_fractions == [mc.fixed_leg_swap_dc_convention(sd, ed) for sd, ed in zip(starts, ends, strict=True)]
            assert swap.fixed_pay_dates[-1] == swap.pay_date

    @pytest.mark.usefixtures('cxx_or_py_zero_rate_curve')
    def test_annuity_calc(self):
        for irate in self.irates:
            zrc = irate['zrc'].payload
            swap = irate['sq']
            num_periods = len(swap.fixed_pay_dates)
            assert swap.annuity_calc(zrc) == swap.annuity_calc(zrc, num_periods), 'annuity default num periods is off'

            #-- the fixed leg annuity
            for num in range(num_periods):
                manual_ann = sum(dcf * df for dcf, df in zip(
                        swap.fixed_dc_fractions[:num + 1],
                        zrc.discount_factors(swap.fixed_pay_dates, today=self.md_basis['md_date'])[:num + 1],
                        strict = True
                    )
                )
                assert manual_ann == swap.annuity_calc(zrc, num + 1)

    @pytest.mark.usefixtures('cxx_or_py_zero_rate_curve')
    def test_swap_rate_calc(self):
        today = self.md_basis['md_date']
        for irate in self.irates:
            zrc  = irate['zrc'].payload
            mc   = irate['mc']
            swap = irate['sq']

            #-- the quoted swap reprices on the curve bootstrapped from it
            assert swap.swap_rate_calc(zrc, today) == pytest.approx(swap.quote, abs = 1.e-10)

            #-- the same as the swap rate from the conventions
            assert swap.swap_rate_calc(zrc, today) == pytest.approx(zrc.swap_rate_simple_compounding(
                swap.start_date, irate['tenor'],
                RDate(freq = mc.fixed_leg_swap_tenor_frequency, count = 1), mc.fixed_leg_swap_dc_convention,
                RDate(freq = mc.tenor_frequency, count = 1), mc.calendar, mc.roll_rule,
                mc.settle_offset, mc.settlement_calendar, mc.roll_rule_to_settle,
                today = today,
            ), abs = 1.e-15)

    def test_periods(self):
        for irate in self.irates:
            swap = irate['sq']
            periods = [(sd, ed, pd, dcf) for sd, ed, pd, dcf in zip( swap.start_dates, swap.end_dates, swap.pay_dates, swap.incremental_dc_fractions, strict=True)]
            assert periods == swap.periods()

    def test_empty_swap(self):
        sq = IRSwapQuotable(mkt_name='SONIA', tenor=RDate('0C'), **self.md_basis)
        assert sq.start_dates == sq.end_dates == sq.pay_dates == sq.periods() == sq.incremental_dc_fractions  == []
        assert sq.fixed_start_dates == sq.fixed_end_dates == sq.fixed_pay_dates == sq.fixed_dc_fractions == []