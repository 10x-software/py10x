from __future__ import annotations

from datetime import date

from core_10x.traitable import M

from xxfin.ccy_cross import CcyCross
from xxfin.fin_instrument import RT, Ccy, FinBasket, FinInstrument, PricingContext, T, XNone
from xxfin.fx_forward_curve import FXFundedDiscRateCurve
from xxfin.fx_mkt_conventions import FXMktConventions


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
        return PricingContext.current().pricing_date

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

    @classmethod
    def funded(cls, denominated: Ccy, end_date: date, funding_ccy: Ccy = None) -> CcyForward:
        """
        A cash flow funded in funding_ccy (USD by default), e.g., a leg of an FX forward:
          - funded in its own ccy, it's just the vanilla CcyForward (discounted on its ccy's own curve), so it nets with
            any other cash flow in that ccy on that date (settlements, lifecycle, other legs)
          - otherwise a CcyForwardFunded (USD funding) or CcyForwardFundedNonUSD (other funding), discounted on the funded
            curve, e.g., GBP|SOFR -- a different instrument, so it does NOT net with a vanilla CcyForward
        """
        funding_ccy = funding_ccy or Ccy.USD()
        if denominated.name == funding_ccy.name:
            return CcyForward(denominated = denominated, end_date = end_date)
        if funding_ccy.is_usd:
            return CcyForwardFunded(denominated = denominated, end_date = end_date)
        return CcyForwardFundedNonUSD(denominated = denominated, end_date = end_date, funding_ccy = funding_ccy)


class CcyForwardFunded(CcyForward):
    """
    A cash flow in `denominated` funded in USD: discounted on the USD-funded curve of the dollar cross, e.g., GBP|SOFR
    (FXFundedDiscRateCurve: the funding curve's accruals adjusted by the FX forward points), not on the ccy's own curve
    (e.g., SONIA), which would treat it as a deposit at a different bank than its USD counterpart.
    USD funding is the standard, so it's not in the ID (denominated|end_date, as the vanilla CcyForward's -- a different
    class, hence a different instrument); a non-USD funding is, see CcyForwardFundedNonUSD.
    Use CcyForward.funded(...) to make one: funded in its own ccy, a cash flow is the vanilla CcyForward.
    Lifecycle as the vanilla CcyForward's: at end_date it becomes CcyUnit, i.e., cash, which nets with any other cash.
    """
    funding_ccy: Ccy    = RT('USD')     ## the standard; not in the ID (see CcyForwardFundedNonUSD)

    def disc_curve_get(self) -> FXFundedDiscRateCurve:
        denom, funding = self.denominated, self.funding_ccy
        assert denom.name != funding.name, f'{self}: funded in its own ccy, use the vanilla CcyForward (CcyForward.funded does)'
        if not funding.is_usd:
            ## TODO: the FX quotables don't carry their funding/collateral ccy yet (they are all USD-collateral quotes), so
            ##      there is nothing to build a non-USD-funded curve from
            raise NotImplementedError(f'{self}: {funding.name}-funded discounting needs {funding.name}-collateral FX quotes')

        cross   = CcyCross.dollar_cross(denom).cross    ## e.g., GBP/USD, USD/JPY
        mc      = FXMktConventions(mkt_name = cross)
        assert mc.funding_rate_mkt_name == funding.discounting_mkt_name, \
            f'{cross}: the funded curve is built on {mc.funding_rate_mkt_name}, but {funding.name} discounts on {funding.discounting_mkt_name} -- the funding leg (vanilla CcyForward) and the funded legs would be inconsistent'

        pc = PricingContext.current()
        return FXFundedDiscRateCurve(
            mkt_name                = cross,
            funding_rate_mkt_name   = funding.discounting_mkt_name,
            provider_name           = pc.mkt_data_provider_name,
            md_date                 = pc.md_date,
            snapshot                = pc.snapshot,
        )


class CcyForwardFundedNonUSD(CcyForwardFunded):
    """CcyForwardFunded with a non-USD funding ccy: the funding is in the ID (denominated|end_date|funding_ccy)"""
    funding_ccy: Ccy    = M(T.ID)
