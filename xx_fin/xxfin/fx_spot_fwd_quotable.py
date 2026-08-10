from __future__ import annotations

from datetime import date

from core_10x.traitable import RT, M, T
from xxcommon.rdate import RDate

from xxfin.fx_mkt_conventions import FXMktConventions
from xxfin.mkt_quotable import SingleMktQuote

class FXSpotQuotable(SingleMktQuote):
    mkt_conventions: FXMktConventions   = M()
    start_date: date                    = M(T.RUNTIME)
    end_date: date                      = M(T.RUNTIME)

    ## TODO: a better way is to have start/end = today/md_date, and pay/settle = spot date = end+offset
    def start_date_get(self) -> date:
        return self.mkt_conventions.spot_date(self.md_date)

    def end_date_get(self) -> date:
        return self.start_date

class FXForwardQuotable(FXSpotQuotable):
    tenor: RDate        = T(T.ID | T.NOT_EMPTY)     // 'e.g., 1W, 3M'
    dc_fraction: float  = RT(T.READONLY)            ## TODO: check if needed

    def dc_fraction_get(self) -> float:
        return self.mkt_conventions.dc_convention(self.start_date, self.end_date)

    ## TODO: similarly to the above, start = md_date, end = start+tenor, pay = end+offset
    def end_date_get(self) -> date:
        mc = self.mkt_conventions
        return self.tenor.apply(self.start_date, mc.calendar, mc.roll_rule)

