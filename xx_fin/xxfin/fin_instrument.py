from datetime import date, datetime

#from core_10x.basket import Basket, T, RT
from core_10x.traitable import RT, T, Traitable

from xxfin.ccy_cross import Ccy, CcyCross
from xxfin.fx_forward_curve import FXForwardCurveSimple
from xxfin.fx_rate import FxRate
from xxfin.ir_rate_mkt_conventions import IRRateMktConventions
from xxfin.ir_zero_rate_curve import ZeroRateCurve
from xxfin.mkt_conventions import MktConventions
from xxfin.pre_basket import PreBasket
from xxfin.pricing_context import PricingContext


class FinInstrument(Traitable):
    denominated: Ccy    = T()
    price: float        = RT()

    disc_curve: ZeroRateCurve       = RT()
    mkt_deps_for_discounting: dict  = RT()

    leaves: PreBasket   = RT()
    mkt_deps: dict      = RT()  ## {quotable_class: basket of quotables}

    ## TODO: why there was "t" argument??
    # def denominated_choices(self, t) -> dict:
    def denominated_choices(self) -> dict:
        return { ccy.name: ccy for ccy in Ccy.load_many() }

    def price_ccy(self, ccy: Ccy) -> float:
        pc = PricingContext.current()
        cross = CcyCross(quote_ccy = ccy, base_ccy = self.denominated)
        fx_rate_object = FxRate(cross_name = cross.cross)
        fx_rate = fx_rate_object.rate(pc.md_date)
        return self.price * fx_rate

    def disc_curve_get(self) -> ZeroRateCurve:
        pc = PricingContext.current()
        return ZeroRateCurve(
            mkt_name        = self.denominated.discounting_mkt_name,
            provider_name   = pc.mkt_data_provider_name,
            md_date         = pc.md_date,
            snapshot        = pc.snapshot,
        )

    ## TODO: seems wrong: returns all rates quotables, not only those max_date
    def mkt_deps_for_discounting_get(self) -> dict:
        return self.disc_curve.quotables_prior_to(self.max_date())

    def leaves_get(self) -> PreBasket:
        return PreBasket() + {self: 1.}

    def discount_factor(self, d: date) -> float:
        pc = PricingContext.current()
        today = pc.md_date
        if d <= today:
            return 1.

        ## denom (USD) -> rate (SOFR) -> Disc Curve -> disc_fact(pay_date)
        zrc = self.disc_curve
        rate_curve = zrc.payload
        #-- TODO: it most probably should be "pricing date", not the md_date (?).
        #-- TODO: if so, PC would need to have a pricing_date with a default value of date.today()
        return rate_curve.discount_factor(d, today)

    def mkt_deps_for_ccy(self, ccy: Ccy) -> dict:
        denom = self.denominated
        if denom == ccy:
            return {}

        pc = PricingContext.current()
        md_basis = pc.md_basis
        max_date = self.max_date()
        _, cross1, _, cross2 = CcyCross.resolve(base_ccy = ccy, quote_ccy = denom)
        fxc = FXForwardCurveSimple(mkt_name = cross1.cross, **md_basis)
        quotables = dict(fxc.quotables_prior_to(max_date))
        if cross2:
            fxc2 = FXForwardCurveSimple(mkt_name = cross2.cross, **md_basis)
            quotables2 = fxc2.quotables_prior_to(max_date)
            for q_cls, objs in quotables2.items():
                ex_objs = quotables.get(q_cls)
                if ex_objs is None:
                    quotables[q_cls] = objs
                else:
                    ex_objs.extend(objs)

        return quotables

    #-- Last date of the instrument, i.e., nothing may change its price after that date
    def max_date(self) -> date:
        raise NotImplementedError    # pragma: no cover

    def mkt_deps_get(self) -> dict:
        raise NotImplementedError    # pragma: no cover


class PerpetualFinInstrument(FinInstrument):
    def max_date(self) -> date:
        return datetime.max.date()

## TODO: should we have a special case of instruments with 1 mkt context
class FinInstrumentSingleMarket(FinInstrument):
    mkt_name: str                   = T(T.ID)
    denominated: Ccy                = RT()      #-- not storable anymore
    mkt_conventions: MktConventions = RT()

    def mkt_conventions_get(self):
        return self.__class__.s_mkt_conventions_class.existing_instance(mkt_name = self.mkt_name)

    def denominated_get(self) -> Ccy:
        return self.mkt_conventions.ccy

    s_mkt_conventions_class = None
    def __init_subclass__(cls, mkt_conventions_class = None, **kwargs):
        if mkt_conventions_class:
            cls.s_mkt_conventions_class = mkt_conventions_class

        assert cls.s_mkt_conventions_class and issubclass(cls.s_mkt_conventions_class, MktConventions), f'{cls} - mkt_conventions_class must be subclass of MktConventions'
        super().__init_subclass__(**kwargs)

