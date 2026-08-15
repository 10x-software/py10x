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
        return self.mkt_conventions.spot_date(self.md_date)

    def end_date_get(self) -> date:
        mc = self.mkt_conventions
        return self.tenor.apply(self.start_date, mc.calendar, mc.roll_rule)

    def pay_date_get(self) -> date:
        return self.mkt_conventions.pay_date(self.end_date)