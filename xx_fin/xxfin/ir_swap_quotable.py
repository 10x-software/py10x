from collections import namedtuple
from datetime import date

from core_10x.traitable import RT, M
from xxcommon.rdate import PROPAGATE_DATES, TENOR_FREQUENCY, RDate

from xxfin.ir_cash_deposit_quotable import IRCashDepositQuotable
from xxfin.ir_rate_mkt_conventions import IRRateMktConventions
from xxfin.rate_curve import RateCurve

SwapsDatesAndFracs = namedtuple('swap_dates_and_dc_fractions', 'start_dates, end_dates, pay_dates, dc_fractions')

class IRSwapQuotable(IRCashDepositQuotable):
    mkt_conventions: IRRateMktConventions = M()

    ## TODO: move to QuoteTemplate
    #-- floating leg
    start_dates: list   = RT()
    end_dates: list     = RT()
    pay_dates: list     = RT()

    incremental_dc_fractions: list = RT()

    #-- fixed leg
    fixed_start_dates: list     = RT()
    fixed_end_dates: list       = RT()
    fixed_pay_dates: list       = RT()
    fixed_dc_fractions: list    = RT()

    #-- a way to have all the swaplet dates/daycount_fracs together
    def periods(self) -> list:
        end_dates = self.end_dates
        if not end_dates:
            return []

        start_dates = self.start_dates
        pay_dates   = self.pay_dates
        incr_fracs  = self.incremental_dc_fractions

        return [
            SwapsDatesAndFracs(start_dates[i], end_dates[i], pay_dates[i], incr_fracs[i])
            for i in range(len(end_dates))
        ]

    def _leg_end_dates(self, freq: TENOR_FREQUENCY) -> list:
        mc = self.mkt_conventions
        #-- the same schedule as the curve's swap legs (see RateCurve.period_dates())
        _, end_dates, _ = RDate(freq = freq, count = 1).period_dates_for_tenor(self.start_date, self.tenor, mc.calendar, mc.roll_rule, PROPAGATE_DATES.BACKWARD, allow_stub = True)
        return end_dates

    def _leg_start_dates(self, end_dates: list) -> list:
        return [self.start_date, *end_dates[:-1]] if end_dates else []

    def end_dates_get(self) -> list:
        return self._leg_end_dates(self.mkt_conventions.tenor_frequency)

    def pay_dates_get(self) -> list:
        mc = self.mkt_conventions
        return [mc.pay_date(ed) for ed in self.end_dates]

    def pay_date_get(self) -> date:
        return self.pay_dates[-1]

    def start_dates_get(self) -> list:
        """
        Not the 1st days of a new period, but the end of the previous one
        to calc rate accrual from the last rate end date to the next w/o gaps
        """
        return self._leg_start_dates(self.end_dates)

    def incremental_dc_fractions_get(self) -> list:
        end_dates = self.end_dates
        start_dates = self.start_dates
        if not start_dates or not end_dates:
            return []

        dc_method = self.mkt_conventions.dc_convention
        return [dc_method(start_dates[i], ed) for i, ed in enumerate(end_dates)]

    def fixed_end_dates_get(self) -> list:
        return self._leg_end_dates(self.mkt_conventions.fixed_leg_swap_tenor_frequency)

    def fixed_start_dates_get(self) -> list:
        return self._leg_start_dates(self.fixed_end_dates)

    def fixed_pay_dates_get(self) -> list:
        mc = self.mkt_conventions
        return [mc.pay_date(ed) for ed in self.fixed_end_dates]

    def fixed_dc_fractions_get(self) -> list:
        dc_method = self.mkt_conventions.fixed_leg_swap_dc_convention
        return [dc_method(sd, ed) for sd, ed in zip(self.fixed_start_dates, self.fixed_end_dates, strict=True)]

    def annuity_calc(self, rate_curve: RateCurve, periods: int = None) -> float:
        """
        The fixed leg annuity of the 1st periods (all by default)
        """
        swap_num_periods = len(self.fixed_pay_dates)
        if periods is None:
            periods = swap_num_periods
        else:
            assert periods >= 0 and periods <= swap_num_periods

        return rate_curve.annuity_for_dc_fractions(self.fixed_dc_fractions[:periods], self.fixed_pay_dates[:periods])

    def swap_rate_calc(self, rate_curve: RateCurve, today: date = None) -> float:
        return rate_curve.swap_rate_for_period_dates(
            self.fixed_dc_fractions, self.fixed_pay_dates,
            self.start_dates, self.end_dates, self.pay_dates,
            today
        )
