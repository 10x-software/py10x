from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import TYPE_CHECKING

import numpy
from core_10x.exec_control import GRAPH_ON, BoundTrait, GraphDeps
from core_10x.rc import RC_TRUE
from core_10x.trait_filter import f
from core_10x.traitable import Bundle
from xxcommon.curve import DateCurve
from xxcommon.rdate import BIZDAY_ROLL_RULE, RDate

from xxfin.mkt_data_basis import RC, RT, M, MktDataBasis, T

if TYPE_CHECKING:
    from xxfin.mkt_adaptor import MktDataAdaptor


#-- TODO: do we need ASSET_CLASS/typename?
class MktQuotable(MktDataBasis):
    start_date: date    = RT()
    end_date: date      = RT()

    pay_date: date      = RT()

    def pay_date_get(self) -> date:
        return self.mkt_conventions.pay_date(self.end_date)

    s_leaf_trait_names = set()
    def __init_subclass__(cls, leaf_traits: tuple = None, inherit_leaf_traits = True, **kwargs):
        super().__init_subclass__(**kwargs)
        if leaf_traits is not None:
            if inherit_leaf_traits:
                cls.s_leaf_trait_names.update(leaf_traits)
            else:
                cls.s_leaf_trait_names = set(leaf_traits)

        assert cls.s_leaf_trait_names, 'leaf_traits may not be empty'
        assert all(cls.trait(name) for name in cls.s_leaf_trait_names), 'leaf_traits must be names of existing traits'


class SingleMktQuote(MktQuotable, leaf_traits = ('quote', )):
    quote: float         = T(fmt = '.6')
    override_ref: Bundle = T() # forward ref to QuotableOverride

    def quote_verify(self,t,q):
        if numpy.isnan(q):
            return RC(False, "quote must not be NaN")
        return RC_TRUE

class MktDeps(GraphDeps):
    def __init__(self, graph: GRAPH_ON, bound_trait: BoundTrait, *target_trait_names, target_class: type[MktQuotable] = None):
        if target_class is None:
            target_class = SingleMktQuote
        if not target_trait_names:
            target_trait_names = target_class.s_leaf_trait_names
        super().__init__(graph, bound_trait, target_class, *target_trait_names)


class QuotableOverride(Bundle,MktDataBasis):
    s_id_override_attr = 'md_date'

    quotable_class: type[MktQuotable] = T(T.ID)

    @classmethod
    def save_many(cls, quotable: MktQuotable, end_date: date = None, **kwargs) -> RC:
        quotable_class = quotable.__class__
        calendar = quotable.mkt_conventions.calendar
        start_date = quotable.md_date
        end_date = end_date or start_date
        dt_range = (date.fromordinal(dt) for dt in range(start_date.toordinal(), end_date.toordinal()+1))
        return sum(
            (
                QuotableOverrideMissingTenor.new_or_update(
                    quotable_class=quotable_class,
                    **cls.id_values(quotable) | {'md_date': dt},
                    **kwargs
                ).save() for dt in dt_range if calendar.is_bizday(dt)
            ),
            RC(True)
        )

    @staticmethod
    def id_values(quotable: MktQuotable):
        return {t.name: quotable.get_value(t.name) for t in type(quotable).traits(flags_on=T.ID)}

    @classmethod
    def find(cls, quotable: MktQuotable):
        found = cls.load_many(
            f(
                f(
                    f(**cls.id_values(quotable)),
                    quotable.__class__.s_bclass,
                ),
                quotable_class = quotable.__class__,
            )
        )
        if found:
            assert len(found) == 1
            return found[0]
        return None

    def id_override_attr_values(self, quotable: MktQuotable) -> tuple[date, date]:
        calendar = quotable.mkt_conventions.calendar
        value = quotable.get_value(self.s_id_override_attr)
        return calendar.prev_bizday(value), calendar.next_bizday(value)

    def quotes(self, quotable, adaptor):
        return [
            adaptor.fill(self.quotable_class(**self.id_values(quotable)|{self.s_id_override_attr: value})).quote
            for value in self.id_override_attr_values(quotable) if value
        ]

    def set_quote(self, quotable: MktQuotable, adaptor: MktDataAdaptor):
        # missing or bad value for date - take an average of the previous date and new one
        quotes = self.quotes(quotable,adaptor)
        quotable.quote = sum(quotes)/len(quotes)

    def fill(self, quotable: MktQuotable, adaptor: MktDataAdaptor):
        self.set_quote(quotable, adaptor)
        quotable.override_ref = self


class QuotableOverrideMissingTenor(QuotableOverride):
    s_id_override_attr = 'tenor'

    tenor: RDate = T(T.ID)
    prev_tenor: RDate = T()
    next_tenor: RDate = T()

    def id_override_attr_values(self, quotable: MktQuotable) -> tuple[RDate, RDate]:
        return self.prev_tenor, self.next_tenor

    def set_quote(self, quotable: MktQuotable, adaptor: MktDataAdaptor):
        # missing or bad value for tenor - linear interpolation between previous and next tenor
        quotes = self.quotes(quotable,adaptor)
        if not self.next_tenor:
            quotable.quote = quotes[0]
            return

        to_date = lambda tenor: tenor.apply(quotable.md_date,quotable.mkt_conventions.calendar, BIZDAY_ROLL_RULE.FOLLOWING)
        quotable.quote = DateCurve(
            dates = [to_date(tenor) for tenor in (self.prev_tenor, self.next_tenor)],
            values = quotes,
            beginning_of_time = to_date(self.prev_tenor),
        ).value(to_date(quotable.tenor))