from __future__ import annotations

from typing import TYPE_CHECKING

from core_10x.traitable import RC, Bundle, T, Traitable
from xxcommon.rdate import RDate

from xxfin.mkt_quotable import MktQuotable

if TYPE_CHECKING:
    from datetime import date


class MktQuotablesScope(Bundle):
    s_data_per_market: dict = None

    concrete_class: type    = T(T.ID)
    mkt_name: str           = T(T.ID)

    quotable_stubs_by_class: dict = T(T.NOT_EMPTY)

    def concrete_class_get(self):
        return self.__class__

    def quotable_class_and_stubs_generator(self, md_date: date):
        for quotable_class, stubs in self.quotable_stubs_by_class.items():
            real_stubs = self.create_quotable_stubs(quotable_class, stubs, md_date)
            for stub in real_stubs:
                yield quotable_class, stub

    def create_quotable_stubs(self, quotable_class: type[MktQuotable], data_definition, md_date: date) -> list:
        raise NotImplementedError

    @classmethod
    def save_scopes(cls, data_per_mkt: dict = None):
        if data_per_mkt is None:
            data_per_mkt = cls.s_data_per_market
        assert data_per_mkt is not None, 'data_per_mkt must be provided'

        for mkt_name, data_per_quotable_class in data_per_mkt.items():
            scope = cls.existing_instance(mkt_name = mkt_name, _throw = False)
            if not scope:
                scope = cls(mkt_name = mkt_name)
                stubs_by_class = {
                    #quotable_class: scope.create_quotable_stubs(quotable_class, data_definition)
                    quotable_class: data_definition
                    for quotable_class, data_definition in data_per_quotable_class.items()
                }

                scope.quotable_stubs_by_class = stubs_by_class
                scope.save().throw()

class TenorBasedQuotablesScope(MktQuotablesScope):
    def create_quotable_stubs(self, quotable_class: type[MktQuotable], data_definition: str, md_date: date) -> list:
        return [ dict(tenor = tenor) for tenor in RDate.from_tenors(data_definition) ]

