from __future__ import annotations

from datetime import date

from core_10x.traitable import T
from xxcommon.curve import DateCurve
from xxcommon.rdate import BIZDAY_ROLL_RULE, PROPAGATE_DATES, TENOR_FREQUENCY, RDate

from xxfin.day_count_convention import DAY_COUNT_CONVENTION
from xxfin.fin_calendar import FinCalendar
from xxfin.ir_compounding import COMPOUND_TRANSFORM, COMPOUNDING, compounding_apply


class RateCurve(DateCurve):
    dc_convention: DAY_COUNT_CONVENTION         = T(DAY_COUNT_CONVENTION.ACT360)    ## use only additive conventions (i.e., not 30/360 variety)
    compounding: COMPOUNDING                    = T(COMPOUNDING.CONTINUOUS)

    quoting_dc_convention: DAY_COUNT_CONVENTION = T(DAY_COUNT_CONVENTION.ACT360)
    quoting_compounding: COMPOUNDING            = T(COMPOUNDING.SIMPLE)

    ## TODO: move the comment!
    ## if ever we have a swap on a non-simple compounded rate then the swap period payout is
    ## curve.fixed_rate_accrual(r, d1, d2, rate params) - curve.accrual_fwd(d1, d2)
    def fixed_rate_accrual(self, r: float, d1: date, d2: date, dc_conv: DAY_COUNT_CONVENTION, compounding: COMPOUNDING) -> float:
        if d1 == d2:
            return 1.

        if d1 > d2: (d1, d2) = (d2, d1)
        t = dc_conv(d1, d2)
        return compounding_apply(compounding, COMPOUND_TRANSFORM.RATE_TO_ACCRUAL, t, r)

    def _today(self, today: date) -> date:
        if today is None:
            today = self.beginning_of_time_as_date()
            assert today, f'{self} - beginning_of_time is not set'
        return today

    def _conventions(self, dc_conv: DAY_COUNT_CONVENTION = None, compounding: COMPOUNDING = None) -> tuple:
        if dc_conv is None:
            dc_conv = self.quoting_dc_convention
        if compounding is None:
            compounding = self.quoting_compounding
        return (dc_conv, compounding)

    def accrual(self, d: date, today: date = None) -> float:
        today = self._today(today)
        if d == today:
            return 1.

        r = self.value(d)
        t = self.dc_convention(today, d)
        return compounding_apply(self.compounding, COMPOUND_TRANSFORM.RATE_TO_ACCRUAL, t, r)

    def accrual_fwd(self, d1: date, d2: date, today: date = None) -> float:
        today = self._today(today)
        if d1 == d2:
            return 1.

        if d1 > d2:
            (d1, d2) = (d2, d1)

        return self.accrual(d2, today) / self.accrual(d1, today)

    def rate_fwd(self, d1: date, d2: date, dc_conv: DAY_COUNT_CONVENTION = None, compounding: COMPOUNDING = None, today: date = None) -> float:
        dc_conv, compounding = self._conventions(dc_conv, compounding)
        today = self._today(today)

        a = self.accrual_fwd(d1, d2, today)
        t = abs(dc_conv(d1, d2))    ## accrual orders dates
        r = compounding_apply(compounding, COMPOUND_TRANSFORM.ACCRUAL_TO_RATE, t, a)

        return r

    def rate(self, d: date, dc_conv: DAY_COUNT_CONVENTION = None, compounding: COMPOUNDING = None, today: date = None) -> float:
        dc_conv, compounding = self._conventions(dc_conv, compounding)
        today = self._today(today)
        a = self.accrual(d, today)
        t = dc_conv(today, d)
        return compounding_apply(compounding, COMPOUND_TRANSFORM.ACCRUAL_TO_RATE, t, a)

    def rate_from_accrual(self, d: date, a: float, dc_conv: DAY_COUNT_CONVENTION = None, compounding: COMPOUNDING = None, today: date = None) -> float:
        dc_conv, compounding = self._conventions(dc_conv, compounding)
        today = self._today(today)
        t = dc_conv(today, d)
        return compounding_apply(compounding, COMPOUND_TRANSFORM.ACCRUAL_TO_RATE, t, a)

    def rate_to_internal(self, rate: float, d:date, dc_conv: DAY_COUNT_CONVENTION, comp: COMPOUNDING, today: date = None) -> float:
        today = self._today(today)
        return self.rate_convert(rate, today, d, dc_conv, comp, self.dc_convention, self.compounding)[0]

    def internal_rate_from_accrual(self, d: date, a: float, today: date = None) -> float:
        return self.rate_from_accrual(d, a, self.dc_convention, self.compounding, today)

    def discount_factor(self, d: date, today: date = None) -> float:
        today = self._today(today)
        return 1. / self.accrual(d, today)

    def discount_factors(self, dates: list[date] = None, today: date = None) -> list[float]:
        today = self._today(today)
        if dates is None:
            dates = self.dates
        return [self.discount_factor(d, today) for d in dates]

    def discount_factors_dates(self, dates: list[date] = None, today: date = None) -> list[tuple[date, float]]:
        today = self._today(today)
        if dates is None:
            dates = self.dates
        return [(d, self.discount_factor(d, today)) for d in dates]

    def discount_factor_fwd(self, d1, d2, today: date = None) -> float:
        return self.discount_factor(d2, today) / self.discount_factor(d1, today)

    def discount_factors_by_date(self, *date_lists: list[date], today: date = None) -> dict:
        """
        One discount factor per distinct date of all the date lists, e.g., dates shared by the swap legs (or by a period end
        and the next period start) are discounted once
        """
        dates = list(dict.fromkeys(d for dates in date_lists for d in dates))
        return dict(zip(dates, self.discount_factors(dates, today), strict=True))

    def annuity_for_dc_fractions(self, dc_fractions: list[float], pay_dates: list[date], today: date = None, dfs: dict = None) -> float:
        """
        sum(dc_fraction_i * df_pay_i) for precomputed day count fractions; dfs (by date) may be shared with the other swap leg
        """
        if dfs is None:
            dfs = self.discount_factors_by_date(pay_dates, today = today)
        return sum(dc_frac * dfs[pay] for dc_frac, pay in zip(dc_fractions, pay_dates, strict=True))

    def annuity_for_period_dates(self, dc_conv: DAY_COUNT_CONVENTION, start_dates: list[date], end_dates: list[date], pay_dates: list[date], today: date = None, dfs: dict = None) -> float:
        assert len(start_dates) == len(end_dates) == len(pay_dates), f'start, end, pay date lists must have the same length: starts/ends/pays: {len(start_dates), len(end_dates), len(pay_dates)}'
        dc_fractions = [dc_conv(start, end) for start, end in zip(start_dates, end_dates, strict=True)]
        return self.annuity_for_dc_fractions(dc_fractions, pay_dates, today, dfs)

    def swap_float_leg_for_period_dates(self, start_dates: list[date], end_dates: list[date], pay_dates: list[date], today: date = None, dfs: dict = None) -> float:
        """
        Simple compounding floating leg: sum((df_start_i/df_end_i - 1) * df_pay_i), see swap_float_leg_simple_compounding();
        dfs (by date) may be shared with the other swap leg
        """
        assert len(start_dates) == len(end_dates) == len(pay_dates), f'start, end, pay date lists must have the same length: starts/ends/pays: {len(start_dates), len(end_dates), len(pay_dates)}'
        if not end_dates:
            return 0.

        if dfs is None:
            #-- the periods are contiguous (start_(i+1) = end_i), so start_dates[1:] are already among end_dates
            dfs = self.discount_factors_by_date(start_dates, end_dates, pay_dates, today = today)

        if pay_dates == end_dates:
            #-- no pay delay: the sum telescopes to df_start_0 - df_end_last
            return dfs[start_dates[0]] - dfs[end_dates[-1]]

        return sum((dfs[start] / dfs[end] - 1.) * dfs[pay] for start, end, pay in zip(start_dates, end_dates, pay_dates, strict=True))

    def period_dates(
        self,
        start_date: date, tenor: RDate, period_freq: RDate, period_calendar: FinCalendar, period_roll_rule: BIZDAY_ROLL_RULE,
        pay_delay: RDate, pay_calendar: FinCalendar, pay_roll_rule: BIZDAY_ROLL_RULE,
        date_propagation: PROPAGATE_DATES = PROPAGATE_DATES.BACKWARD, allow_stub: bool = True
    ) -> tuple:
        start_dates, end_dates, _ = period_freq.period_dates_for_tenor(start_date, tenor, period_calendar, period_roll_rule, date_propagation, allow_stub)
        pay_dates = [pay_delay.apply(ed, pay_calendar, pay_roll_rule) for ed in end_dates]

        return start_dates, end_dates, pay_dates

    def annuity(
        self,
        dc_conv: DAY_COUNT_CONVENTION,
        start_date: date, tenor: RDate, period_freq: RDate, period_calendar: FinCalendar, period_roll_rule: BIZDAY_ROLL_RULE,
        pay_delay: RDate, pay_calendar: FinCalendar, pay_roll_rule: BIZDAY_ROLL_RULE,
        date_propagation: PROPAGATE_DATES = PROPAGATE_DATES.BACKWARD, allow_stub: bool = True,
        today: date = None
    ) -> float:
        start_dates, end_dates, pay_dates = self.period_dates(start_date, tenor, period_freq, period_calendar, period_roll_rule, pay_delay, pay_calendar, pay_roll_rule, date_propagation, allow_stub)

        return self.annuity_for_period_dates(dc_conv, start_dates, end_dates, pay_dates, today)

    ## If rate compounding is SIMPLE then each swaplet payout is (fixed_rate - float_rate) * dc_fraction * disc_factor
    ## otherwise (never happens!) the payout would've been (fixed_rate_accrual - floating_rate_accrual) * disc_factor
    ## and the swap par rate formula wouldn't telescope to the neat beauty we all have learned in pre-K
    def swap_float_leg_simple_compounding(
        self,
        start_date: date, tenor: RDate,
        swap_freq: RDate,
        swap_calendar: FinCalendar, swap_roll_rule: BIZDAY_ROLL_RULE,
        pay_delay:  RDate, pay_calendar: FinCalendar,  pay_roll_rule: BIZDAY_ROLL_RULE,
        date_propagation: PROPAGATE_DATES = PROPAGATE_DATES.BACKWARD, allow_stub: bool = True, today: date = None
    ) -> float:

        if not pay_delay.count:
            end_date = tenor.apply(start_date, swap_calendar, swap_roll_rule)
            last_pay = pay_delay.apply(end_date, pay_calendar, pay_roll_rule)

            df_last = self.discount_factor(last_pay,   today)
            df_spot = self.discount_factor(start_date, today)

            return (df_spot - df_last)

        start_dates, end_dates, pay_dates = self.period_dates(start_date, tenor,
                                                              swap_freq, swap_calendar,
                                                              swap_roll_rule,
                                                              pay_delay, pay_calendar,
                                                              pay_roll_rule, date_propagation, allow_stub)

        ## the general formula below may be decomposed into 2 parts.
        ## denote the (undiscounted) coupon of period i: c_i = df_start_i/df_end_i - 1  (= float_rate_i * dc_fraction_i)
        ## the floating leg = sum(c_i * df_pay_i)
        ##                  = sum(c_i * df_end_i) - sum(c_i * (df_end_i/df_pay_i - 1) * df_pay_i)
        ## i.e., the coupons discounted from the **end_date** (!= pay_date in general)
        ## minus the coupons' accrual over the end_date-to-pay_date period, discounted from the pay_date.
        ## in other words, the coupons' value is reduced by (the lender's funding of) the non-payment/"free" period from end_date to pay_date
        ## and sum(c_i * df_end_i) = sum(df_start_i - df_end_i) telescopes to df_start_0 - df_end_last as in the good old libor swap...
        ## so the no arb argument is as follows:
        ## -- borrower gets the notional day1 (pv = df_start_0),
        ## -- pays the stream of the period coupons
        ## -- returns the notional at the end (pv = df_end_last)
        ## -- gets the benefit of the free carry of the period coupons over end_date-to-pay_date period

        ## full payment
        #     ( self.discount_factor(start, today)
        #     / self.discount_factor(end, today) - 1)
        #     * self.discount_factor(pay, today)
        # =
        ## non-delayed coupon
        #     ( self.discount_factor(start, today)
        #     / self.discount_factor(end, today) - 1)
        #     * self.discount_factor(end, today)
        # -
        ## the coupon accrual over end_to_pay period
        #     ( self.discount_factor(start, today)
        #     / self.discount_factor(end, today) - 1)
        #   * ( self.discount_factor(end, today)
        #     / self.discount_factor(pay, today) - 1)
        ## paid on pay date
        #     * self.discount_factor(pay, today)
        #
        ## the non-delayed coupon:
        #     ( self.discount_factor(start, today)
        #     / self.discount_factor(end, today) - 1)
        #     * self.discount_factor(end, today)
        # =   ( self.discount_factor(start, today) - self.discount_factor(end, today)
        ## hence the telescoping sum = self.discount_factor(start_0, today) - self.discount_factor(end_last, today)
        ## and the "simple" no arb description

        return self.swap_float_leg_for_period_dates(start_dates, end_dates, pay_dates, today)

    def swap_rate_simple_compounding(
        self,
        spot_date: date, tenor: RDate,
        fixed_freq: RDate, fixed_dc_convention: DAY_COUNT_CONVENTION,
        swap_freq: RDate, swap_calendar: FinCalendar, swap_roll_rule: BIZDAY_ROLL_RULE,
        pay_delay:  RDate, pay_calendar: FinCalendar,  pay_roll_rule: BIZDAY_ROLL_RULE,
        date_propagation: PROPAGATE_DATES = PROPAGATE_DATES.BACKWARD, allow_stub: bool = True, today: date = None
    ) -> float:

        fixed_starts, fixed_ends, fixed_pays = self.period_dates(
            spot_date, tenor, fixed_freq, swap_calendar, swap_roll_rule,
            pay_delay, pay_calendar, pay_roll_rule,
            date_propagation, allow_stub,
        )
        float_starts, float_ends, float_pays = self.period_dates(
            spot_date, tenor, swap_freq, swap_calendar, swap_roll_rule,
            pay_delay, pay_calendar, pay_roll_rule,
            date_propagation, allow_stub,
        )
        fixed_dc_fractions = [fixed_dc_convention(start, end) for start, end in zip(fixed_starts, fixed_ends, strict=True)]

        return self.swap_rate_for_period_dates(fixed_dc_fractions, fixed_pays, float_starts, float_ends, float_pays, today)

    def swap_rate_for_period_dates(
        self,
        fixed_dc_fractions: list[float], fixed_pay_dates: list[date],
        float_start_dates: list[date], float_end_dates: list[date], float_pay_dates: list[date],
        today: date = None
    ) -> float:
        """
        Simple compounding swap par rate for the given (precomputed) leg schedules: float_leg / fixed_leg_annuity
        """
        #-- one discount factor per date: the legs share most of the dates (all of them if the fixed and floating frequencies are the same)
        dfs = self.discount_factors_by_date(fixed_pay_dates, float_start_dates, float_end_dates, float_pay_dates, today = today)

        float_leg = self.swap_float_leg_for_period_dates(float_start_dates, float_end_dates, float_pay_dates, today, dfs)
        annuity   = self.annuity_for_dc_fractions(fixed_dc_fractions, fixed_pay_dates, today, dfs)
        return float_leg / annuity

    @classmethod
    def rate_convert(
        cls,
        r_init: float,
        d1: date, d2: date,
        dc_convention_init: DAY_COUNT_CONVENTION, compounding_init: COMPOUNDING,
        dc_convention_conv: DAY_COUNT_CONVENTION, compounding_conv: COMPOUNDING
    ) -> tuple:  #-- (coverted rate, converted dc_fraction)
        t_init = dc_convention_init(d1, d2)
        t_conv = dc_convention_conv(d1, d2)
        acc    = compounding_apply(compounding_init, COMPOUND_TRANSFORM.RATE_TO_ACCRUAL, t_init, r_init)
        r_conv = compounding_apply(compounding_conv, COMPOUND_TRANSFORM.ACCRUAL_TO_RATE, t_conv, acc)

        return (r_conv, t_conv)

## Baaaad name
class AccrualRatioCurve(DateCurve):
    over_curve: RateCurve   = T(T.EMBEDDED)
    under_curve: RateCurve  = T(T.EMBEDDED)
    scale: float            = T()

    def value(self, d: date) -> float:
        over_accrual = self.over_curve.accrual(d)
        under_accrual = self.under_curve.accrual(d)

        return over_accrual / under_accrual * self.scale
