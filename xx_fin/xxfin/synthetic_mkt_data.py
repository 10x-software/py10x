from __future__ import annotations

import bisect
from typing import TYPE_CHECKING, Any

from core_10x.traitable import RT, M, T, Traitable
from core_10x.xnone import XNone
from xxcommon.rdate import RDate

from xxfin.mkt_data_basis import MktDataBasis
from xxfin.mkt_quotables_scope import MktQuotablesScope

if TYPE_CHECKING:
    from datetime import date


class MktAssembly(Traitable):
    s_mas_data_per_market: dict = None
    def __init_subclass__(cls, **kwargs):
        assert cls.s_mas_data_per_market, f'{cls} - s_mas_data_per_market is not defined'
        super().__init_subclass__(**kwargs)

    mkt_name: str   = T(T.ID)
    data: dict      = T()

    def data_get(self) -> dict:
        cls = self.__class__
        data = cls.s_mas_data_per_market.get(self.mkt_name)
        assert data is not None, f'{cls}: No Market Assembly data found for {self.mkt_name}'
        return data

    @classmethod
    def convert_from_tenor_str(cls, data: dict) -> dict:
        return { quotable_cls: RDate.from_tenors(value) for quotable_cls, value in data.items() }

    @classmethod
    def convert_data(cls, data: dict) -> dict:
        return data

class SyntheticMktDataWithoutMas(MktDataBasis):
    payload: Any    = T()

class SyntheticMktData(SyntheticMktDataWithoutMas):
    s_mas_class = None
    def __init_subclass__(cls, mas_class = None, **kwargs):
        if mas_class is not XNone:
            if mas_class is not None:
                cls.s_mas_class = mas_class

            assert cls.s_mas_class, f'{cls} - Market Assembly class is not defined'

        super().__init_subclass__(**kwargs)

    mkt_assembly_object: MktQuotablesScope  = T()
    mkt_assembly: dict                      = RT()

    def mkt_assembly_object_get(self):
        cls = self.__class__
        return cls.s_mas_class.existing_instance(mkt_name = self.mkt_name)

    def mkt_assembly_get(self) -> dict:
        return self.mkt_assembly_object.quotable_stubs_by_class

class TenorBasedSyntheticCurve(SyntheticMktData, mas_class = XNone):
    quotables_by_class: dict            = RT()
    dates_quotables_map: tuple          = RT()

    def quotables_by_class_get(self):   raise NotImplementedError

    def dates_quotables_map_get(self) -> tuple:
        dates = []
        aligned_quotables = []
        res = (dates, aligned_quotables)

        sortable_quotables = [ (d, quotable) for quotables_by_date in self.quotables_by_class.values() for d, quotable in quotables_by_date.items() ]
        sorted_quotables = sorted(sortable_quotables, key = lambda q: q[0])
        cur_quotables_by_class = {}
        for (d, quotable) in sorted_quotables:
            quotables_by_class = dict(cur_quotables_by_class)
            cur_class = quotable.__class__
            ex_quotables = list(quotables_by_class.setdefault(cur_class, []))
            ### ex_quotables = quotables_by_class.setdefault(cur_class, [])
            ex_quotables.append(quotable)
            quotables_by_class[cur_class] = ex_quotables

            dates.append(d)
            aligned_quotables.append(quotables_by_class)
            cur_quotables_by_class = quotables_by_class

        return res

    def quotables_prior_to(self, max_date: date) -> dict:
        dates, quotables_by_class = self.dates_quotables_map
        i = bisect.bisect_left(dates, max_date)
        if i == len(dates):
            i -= 1

        return quotables_by_class[i]
