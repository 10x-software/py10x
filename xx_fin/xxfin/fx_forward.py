from __future__ import annotations

from datetime import date

from core_10x.traitable import M

from xxfin.ccy_forward import CcyForward
from xxfin.fin_instrument import RT, Ccy, FinBasket, FinInstrument, PricingContext, T, XNone


class FXForward(FinInstrument):
    """
    FX forward: receive 1 base_ccy and pay forward_rate quote_ccy on end_date (the value date), e.g., GBP/USD @ 1.33:
    +1 GBP, -1.33 USD. The two legs are funded together in funding_ccy (USD, the standard): only the difference is funded,
    not each leg separately as deposits in two different banks.

    Prices as its 2 legs (leaves), each CcyForward.funded(ccy, end_date, funding_ccy):
      - the funding ccy's leg is the vanilla CcyForward, on its own curve (e.g., SOFR)
      - any other leg is funded, on the funded curve (e.g., GBP|SOFR)
    so a dollar cross is SOFR + one funded curve, and a non-dollar cross (e.g., EUR/GBP) is 2 funded curves (EUR|SOFR, GBP|SOFR).
    Price in quote_ccy (denominated); the base leg is converted at the FX rate on the pricing date.

    USD funding is not in the ID (base_ccy|quote_ccy|end_date|forward_rate); a non-USD funding is, see FXForwardFunded.
    Lifecycle: at end_date the legs become cash (CcyUnit's).
    """
    base_ccy: Ccy           = RT(T.ID)
    quote_ccy: Ccy          = RT(T.ID)
    end_date: date          = RT(T.ID)      // 'value date'
    forward_rate: float     = RT(T.ID)      // 'quote_ccy per 1 base_ccy'

    denominated: Ccy        = RT()
    funding_ccy: Ccy        = RT('USD')     ## the standard; not in the ID (see FXForwardFunded)

    def denominated_get(self) -> Ccy:
        return self.quote_ccy

    def base_leg(self) -> CcyForward:
        return CcyForward.funded(self.base_ccy, self.end_date, self.funding_ccy)

    def quote_leg(self) -> CcyForward:
        return CcyForward.funded(self.quote_ccy, self.end_date, self.funding_ccy)

    def leaves_get(self) -> FinBasket:
        return FinBasket.of((self.base_leg(), 1.), (self.quote_leg(), -self.forward_rate))

    def price_get(self) -> float:
        quote = self.quote_ccy
        return sum((leaf.price if leaf.denominated.name == quote.name else leaf.price_ccy(quote)) * qty for leaf, qty in self.leaves.members_qtys())

    def max_date(self) -> date:
        return self.end_date

    def next_lifecycle_date(self, after: date) -> date:
        ed = self.end_date
        return ed if after < ed else XNone

    def lifecycle_transform(self) -> FinBasket:
        if PricingContext.current().md_date < self.end_date:
            return XNone
        return self.leaves.fire_lifecycle()


class FXForwardFunded(FXForward):
    """FXForward with a non-USD funding ccy: the funding is in the ID (base_ccy|quote_ccy|end_date|forward_rate|funding_ccy)"""
    funding_ccy: Ccy        = M(T.ID)
