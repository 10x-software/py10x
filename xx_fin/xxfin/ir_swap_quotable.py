from collections import namedtuple

import numpy
from core_10x.traitable import RT, M
from xxcommon.rdate import PROPAGATE_DATES, RDate

from xxfin.ir_cash_deposit_quotable import IRCashDepositQuotable
from xxfin.ir_rate_mkt_conventions import IRRateMktConventions
from xxfin.rate_curve import RateCurve

SwapsDatesAndFracs = namedtuple('swap_dates_and_dc_fractions', 'start_dates, end_dates, pay_dates, dc_fractions')

class IRSwapQuotable(IRCashDepositQuotable):
    mkt_conventions: IRRateMktConventions = M()

    ## TODO: check if the below is used
    ## TODO: move to QuoteTemplate if used
    start_dates: list   = RT()
    end_dates: list     = RT()
    pay_dates: list     = RT()

    incremental_dc_fractions: list = RT()

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

    def end_dates_get(self) -> list:
        # Annuity accrues the fixed leg. Stepping while the previous date is still
        # before maturity appends one full period past a non-integral tenor.
        mc = self.mkt_conventions
        fixed_freq = RDate(freq=mc.fixed_leg_swap_tenor_frequency, count=1)
        _, end_dates, _ = fixed_freq.period_dates_for_tenor(
            self.start_date, self.tenor, mc.calendar, mc.roll_rule,
            PROPAGATE_DATES.FORWARD, True,
        )
        return end_dates

    def pay_dates_get(self) -> list:
        end_dates = self.end_dates
        mc = self.mkt_conventions
        return [mc.pay_date(ed) for ed in end_dates]

    def start_dates_get(self) -> list:
        """
        Not the 1st days of a new period, but the end of the previous one
        to calc rate accrual from the last rate end date to the next w/o gaps
        """
        end_dates = self.end_dates
        return [self.start_date, *end_dates[:-1]] if end_dates else []

    def incremental_dc_fractions_get(self) -> list:
        end_dates = self.end_dates
        start_dates = self.start_dates
        if not start_dates or not end_dates:
            return []

        dc_method = self.mkt_conventions.dc_convention
        return [dc_method(start_dates[i], ed) for i, ed in enumerate(end_dates)]

    def annuity_calc(self, rate_curve: RateCurve, periods: int = None) -> float:
        swap_num_periods = len(self.pay_dates)
        if periods is None:
            periods = swap_num_periods
        else:
            assert periods >= 0 and periods <= swap_num_periods

        return rate_curve.annuity_for_period_dates(
            self.mkt_conventions.dc_convention,
            self.start_dates[:periods],
            self.end_dates[  :periods],
            self.pay_dates[  :periods]
        )
