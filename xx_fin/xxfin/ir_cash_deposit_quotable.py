from __future__ import annotations

from typing import TYPE_CHECKING

from core_10x.traitable import RT, M, T
from xxcommon.rdate import RDate

from xxfin.ir_compounding import COMPOUND_TRANSFORM, COMPOUNDING
from xxfin.ir_rate_mkt_conventions import IRRateMktConventions
from xxfin.mkt_quotable import SingleMktQuote

if TYPE_CHECKING:
    from datetime import date


class IRCashDepositQuotable(SingleMktQuote):
    mkt_conventions: IRRateMktConventions = M()

    tenor: RDate        = T(T.ID | T.NOT_EMPTY)     // 'e.g., 1W, 3M'

    ## TODO: where the below is used??

    ## TODO: should move to QuoteTemplate
#     dc_fraction: float  = RT(T.READONLY)
#
#     def dc_fraction_get(self) -> float:
#         return self.mkt_conventions.dc_convention(self.start_date, self.end_date)
#
    def start_date_get(self) -> date:
        return self.mkt_conventions.spot_date(self.md_date)
    def end_date_get(self) -> date:
        mc = self.mkt_conventions
        return self.tenor.apply(self.start_date, mc.calendar, mc.roll_rule)

    def pay_date_get(self) -> date:
        return self.mkt_conventions.pay_date(self.end_date)

#     def accrual(self, compounding: COMPOUNDING = None) -> float:
#         if compounding is None:
#             compounding = self.mkt_conventions.compounding
#
#         return COMPOUNDING_TRANSFORM_TABLE[compounding][COMPOUND_TRANSFORM.RATE_TO_ACCRUAL](self.dc_fraction, self.quote)
#
# class IRCashDepositQuoteTemplate(IRCashDepositQuotable):
#     dc_fraction: float  = RT(T.READONLY)
#
#     def dc_fraction_get(self) -> float:
#         return self.mkt_conventions.dc_convention(self.start_date, self.end_date)
#
#     def start_date_get(self) -> date:
#         return self.mkt_conventions.spot_date(self.md_date)
#
#     def end_date_get(self) -> date:
#         mc = self.mkt_conventions
#         return self.tenor.apply(self.start_date, mc.calendar, mc.roll_rule)
#
#     def accrual(self, compounding: COMPOUNDING = None) -> float:
#         if compounding is None:
#             compounding = self.mkt_conventions.compounding
#
#         return COMPOUNDING_TRANSFORM_TABLE[compounding][COMPOUND_TRANSFORM.RATE_TO_ACCRUAL](self.dc_fraction, self.quote)
