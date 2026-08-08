from collections import namedtuple

import numpy
from core_10x.traitable import RT, M
from xxcommon.rdate import FREQUENCY_TABLE, TENOR_PARAMS, RDate

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

    #-- TODO: for some reason(s) most of the getters return empty results - fix!
    def end_dates_get(self) -> list:
        mc = self.mkt_conventions
        cal = mc.calendar
        roll_rule = mc.roll_rule

        freq_method = FREQUENCY_TABLE[self.tenor.freq][TENOR_PARAMS.RDATE_FUNC]
        freq_step   = self.tenor.count
        raw_ed = rolled_ed = self.start_date
        swap_end_date = self.end_date
        end_dates = []
        while rolled_ed < swap_end_date:
            raw_ed = freq_method(raw_ed, freq_step)
            rolled_ed = RDate.roll_to_bizday(raw_ed, cal, roll_rule)
            end_dates.append(rolled_ed)

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

    def incremental_daycount_fracs_get(self) -> list:
        end_dates = self.end_dates
        start_dates = self.start_dates
        if not start_dates or not end_dates:
            return []

        dc_method = self.mkt_conventions.dc_convention
        return [dc_method(start_dates[i], ed) for i, ed in enumerate(end_dates)]

    def annuity_calc(self, rate_curve: RateCurve, periods: int = None) -> float:
        dfs = rate_curve.values_at(self.pay_dates)
        num_periods = len(dfs)
        if periods is None:
            periods = num_periods
        else:
            assert periods >= 0 and periods <= num_periods

        incr_fracs = self.incremental_dc_fractions
        assert len(incr_fracs), 'empty swap??'

        x = numpy.dot(dfs[:periods], incr_fracs[:periods])
        try:
            return float(x)
        except Exception:
            return x[0]     #-- numpy.dot() os f'd-up

