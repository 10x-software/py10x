from __future__ import annotations

from typing import TYPE_CHECKING

from core_10x.trait_definition import RT
from core_10x.traitable import Traitable

if TYPE_CHECKING:
    from collections.abc import Callable


class PreBasket(Traitable):
    contents: dict  = RT({})

    # def __repr__(self) -> str:
    #     dd = {}
    #     for (k,v) in self.contents.items():
    #         if isinstance(k, Traitable):
    #             k = k.id()
    #         dd[k] = v
    #     print(dd)
    #     return f'PreBasket(contents={dd})'
        # return f'PreBasket(contents={self.contents})'

    def multadd(self, mult: float, add, keep_zeros = False, zero_qty_tolerance = 1.e-10) -> PreBasket:
        if not keep_zeros and abs(mult) < abs(zero_qty_tolerance):
            return PreBasket()

        if add:
            if not isinstance(add, (PreBasket, dict)):
                raise TypeError("add must be a PreBasket or dict object")
            if isinstance(add, dict):
                cont_add = add
            else:
                cont_add = add.contents
        else:
            cont_add = {}

        cont_self = self.contents

        cont = {k: v * mult for k, v in cont_self.items()}
        for k, v in cont_add.items():
            cont[k] = v if k not in cont_self else cont[k] + v

        result = PreBasket(contents = cont)
        if not keep_zeros:
            return result.prune_zeros(zero_qty_tolerance)

        return result

    def prune_zeros(self, zero_qty_tolerance = 1.e-10) -> PreBasket:
        c = self.contents
        return PreBasket(contents = {k: v for k, v in c.items() if abs(v) > abs(zero_qty_tolerance)})

    def __mul__(self, other: float) -> PreBasket:
        if isinstance(other, (int, float)):
            return self.multadd(other, None)
        raise ValueError(f'Cannot multiply PreBasket by {other}, because it is not a number')

    def __rmul__(self, other: float) -> PreBasket:
        if isinstance(other, (int, float)):
            return self.multadd(other, None)
        raise ValueError(f'Cannot multiply PreBasket by {other}, because it is not a number')

    def __truediv__(self, other: float) -> PreBasket:
        if isinstance(other, (int, float)):
            return self.multadd(1/other, None)
        raise ValueError(f'Cannot divide PreBasket by {other}, because it is not a number')

    def __add__(self, other) -> PreBasket:
        return self.multadd(1.0, other)

    def __sub__(self, other) -> PreBasket:
        minus_me = self * (-1)
        minus_me_plus_other = minus_me + other
        return minus_me_plus_other * (-1)       ## to cover the case of other = dict use basket - other = ((basket*(-1) + other)*(-1)

    def __iadd__(self, other: PreBasket):   ## TODO; doesnt work
        self.contents = (self + other).contents
        # self.contents = self.multadd(1.0, other).contents

    def __isub__(self, other: PreBasket):
        self.contents = self.multadd(1.0, other.multadd(-1., None)).contents

    def __imul__(self, other: float):
        self.contents = (self.multadd(other, None)).contents

    def __len__(self) -> bool:
        return len(self.contents)

    def __bool__(self) -> bool:
        # return not self.contents
        return len(self.contents) > 0

    def add(self, other: PreBasket, keep_zeros = False, zero_qty_tolerance = 1.e-10) -> PreBasket:
        return self.multadd(1, other, keep_zeros = keep_zeros, zero_qty_tolerance = zero_qty_tolerance)

    def add_many(self, many_adds: list, keep_zeros = False, zero_qty_tolerance = 1.e-10) -> PreBasket:
        return sum((self.add(add, keep_zeros = keep_zeros, zero_qty_tolerance = zero_qty_tolerance) for add in many_adds), PreBasket())

    def mult(self, other: float, keep_zeros = False, zero_qty_tolerance = 1.e-10) -> PreBasket:
        return self.multadd(other, None, keep_zeros = keep_zeros, zero_qty_tolerance = zero_qty_tolerance)

    def apply_func(self, func: Callable) -> float:
        return sum(func(k) * v for k, v in self.contents.items())

    def sum_of_weights(self) -> float:
        return self.apply_func(lambda x: 1)

    ## likely non-kosher, but can use this for price (and later for leaves, if change the summation)
    def get_weighted_value(self, val_name:str, zero_for_value_type = 0.):
        return sum((k.get_value(val_name) * v for k, v in self.contents.items()), zero_for_value_type)

    ## to handle price_ccy(ccy)
    def get_weighted_attr(self, attr_name, **kwargs):
        return sum((attr(**kwargs) if callable(attr) else attr) * v for k, v in self.contents.items() for attr in [getattr(k, attr_name)])

    def get_constituent_numeric_values(self, val_name:str):
        return PreBasket() + {k: k.get_value(val_name) * v for k, v in self.contents.items()}
