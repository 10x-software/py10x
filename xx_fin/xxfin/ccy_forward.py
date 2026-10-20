from __future__ import annotations

from datetime import date

from xxfin.fin_instrument import RT, Ccy, FinBasket, FinInstrument, PricingContext, T, XNone


class CcyUnit(FinInstrument):
    denominated: Ccy    = RT(T.ID)   #-- became non-storable ID

    ## TODO: retired in favor of runtime discovery via GraphDeps/MktDeps (see mkt_deps_design_notes.md) --
    ##       kept commented for possible future use in simulation scenarios. OK to discard instead?
    # def mkt_deps_get(self) -> dict:
    #     return {}
    #
    # def mkt_deps_for_discounting_get(self) -> dict:
    #     return {}

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

    def next_lifecycle_date(self, after: date) -> date:
        ed = self.end_date
        return ed if after < ed else XNone

    def lifecycle_transform(self) -> FinBasket:
        if PricingContext.current().md_date < self.end_date:
            return XNone

        return FinBasket.of((CcyUnit(denominated = self.denominated), 1.0))

    ## TODO: retired -- see note above
    # def mkt_deps_get(self) -> dict:
    #     return self.mkt_deps_for_discounting
