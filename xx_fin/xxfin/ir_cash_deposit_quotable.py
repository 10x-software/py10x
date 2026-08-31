from __future__ import annotations

from datetime import date

from core_10x.traitable import RT, M, T
from xxcommon.rdate import RDate

from xxfin.ir_compounding import COMPOUND_TRANSFORM, COMPOUNDING
from xxfin.ir_rate_mkt_conventions import IRRateMktConventions
from xxfin.mkt_quotable import SingleMktQuote


class IRCashDepositQuotable(SingleMktQuote):
    mkt_conventions: IRRateMktConventions = M()

    tenor: RDate        = T(T.ID | T.NOT_EMPTY)     // 'e.g., 1W, 3M'

    def start_date_get(self) -> date:
        #-- the O/N ('1B') deposit actually starts today, not at spot -- previously this trait
        #   ignored that and always returned spot_date, which was silently correct only because
        #   ZeroRateCurve.quotables_by_class_get()/process_cash_deposits() each independently
        #   re-derived the real start date with their own 'today if 1B else spot_date' check
        #   instead of trusting this trait. Any new caller reading quotable.start_date directly
        #   (e.g. QL.deposit_helper) would silently get the wrong start date for O/N without this.
        if self.tenor.symbol() == '1B':
            return self.md_date
        return self.mkt_conventions.spot_date(self.md_date)

    def end_date_get(self) -> date:
        mc = self.mkt_conventions
        return self.tenor.apply(self.start_date, mc.calendar, mc.roll_rule)

    def pay_date_get(self) -> date:
        return self.mkt_conventions.pay_date(self.end_date)