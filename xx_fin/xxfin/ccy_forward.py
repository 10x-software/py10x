from __future__ import annotations

from typing import TYPE_CHECKING

from xxfin.fin_instrument import RT, Ccy, FinInstrument, PricingContext, T

if TYPE_CHECKING:
    from datetime import date


class CcyUnit(FinInstrument):
    denominated: Ccy    = RT(T.ID)   #-- became non-storable ID

    def mkt_deps_get(self) -> dict:
        return {}

    def mkt_deps_for_discounting_get(self) -> dict:
        return {}

    def price_get(self) -> float:
        return 1.

    def max_date(self) -> date:
        return PricingContext.current().md_date

class CcyForward(FinInstrument):
    denominated: Ccy    = RT(T.ID)   #-- became non-storable ID
    end_date: date      = RT(T.ID)

    def price_get(self) -> float:
        return self.discount_factor(self.end_date)

    def max_date(self) -> date:
        return self.end_date

    def mkt_deps_get(self) -> dict:
        return self.mkt_deps_for_discounting
