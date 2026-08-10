from __future__ import annotations

from typing import TYPE_CHECKING

from core_10x.traitable import T
from xxcommon.curve import DateCurve
from xxcommon.rdate import BIZDAY_ROLL_RULE, PROPAGATE_DATES, TENOR_FREQUENCY, RDate

from xxfin.day_count_convention import DAY_COUNT_CONVENTION
from xxfin.fin_calendar import FinCalendar
from xxfin.ir_compounding import COMPOUND_TRANSFORM, COMPOUNDING, compounding_apply

if TYPE_CHECKING:
    from datetime import date


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

    def annuity(
        self,
        dc_conv: DAY_COUNT_CONVENTION,
        start_date: date, tenor: RDate, period_freq: RDate, period_calendar: FinCalendar, period_roll_rule: BIZDAY_ROLL_RULE,
        pay_delay: RDate, pay_calendar: FinCalendar, pay_roll_rule: BIZDAY_ROLL_RULE,
        date_propagation: PROPAGATE_DATES = PROPAGATE_DATES.BACKWARD, allow_stub: bool = True, today: date = None
    ) -> float:
        start_dates, end_dates, _ = period_freq.period_dates_for_tenor(start_date, tenor, period_calendar, period_roll_rule, date_propagation, allow_stub)
        pay_dates = [pay_delay.apply(ed, pay_calendar, pay_roll_rule) for ed in end_dates]

        return sum(dc_conv(start, end) * self.discount_factor(pay, today) for start, end, pay in zip(start_dates, end_dates, pay_dates, strict=True))

    ## If rate compounding is SIMPLE then each swaplet payout is (fixed_rate - float_rate) * dc_fraction * disc_factor
    ## otherwise (never happens!) the payout would've been (fixed_rate_accrual - floating_rate_accrual) * disc_factor
    ## and the swap par rate formula wouldn't telescope to the neat beauty we all have learned in pre-K
    def swap_rate_simple_compounding(
        self,
        spot_date: date, tenor: RDate,
        fixed_freq: RDate, fixed_dc_convention: DAY_COUNT_CONVENTION, swap_calendar: FinCalendar, swap_roll_rule: BIZDAY_ROLL_RULE,
        pay_delay:  RDate, pay_calendar: FinCalendar,  pay_roll_rule: BIZDAY_ROLL_RULE,
        date_propagation: PROPAGATE_DATES = PROPAGATE_DATES.BACKWARD, allow_stub: bool = True, today: date = None
    ) -> float:

        df_spot = self.discount_factor(spot_date, today)

        spot_annuity = self.annuity(
            fixed_dc_convention, spot_date, tenor,
            fixed_freq, swap_calendar, swap_roll_rule,
            pay_delay,  pay_calendar,  pay_roll_rule,
            date_propagation, allow_stub, today
        ) / df_spot

        end_date = tenor.apply(spot_date, swap_calendar, swap_roll_rule)
        last_pay = pay_delay.apply(end_date, pay_calendar, pay_roll_rule)

        df_last_to_spot = self.discount_factor(last_pay, today) / df_spot

        swap_rate = (1. - df_last_to_spot) / spot_annuity
        return swap_rate

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
