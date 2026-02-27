from __future__ import annotations
from typing import Self

from core_10x.traitable import Traitable, T, RT, RC, RC_TRUE
from core_10x.trait_filter import f


class BasketLike(Traitable):
    s_constituent_classes       = set()
    s_is_container              = False
    s_is_cumulative             = False

    def __init_subclass__(cls, is_base_class = False, may_contain = (), **kwargs):
        if not is_base_class:
            assert may_contain or cls.s_constituent_classes, 'may_contain must specify one or more constituent classes'
            if may_contain:
                assert type(may_contain) is tuple and all(issubclass(c, BasketLike) for c in may_contain), 'may_contain must be a tuple of subclasses of BasketLike'
                cls.s_constituent_classes = set(may_contain)

    may_contain_subclasses: bool        = RT(False)
    may_contain_self: bool              = RT(False)
    constituents: list[BasketLike]      = RT()
    basket: dict[BasketLike, float]     = RT()

    def is_member(self, other: BasketLike) -> bool:
        return other in self.basket

    def check_new_constituent(self, other: BasketLike) -> RC:
        cls = self.__class__
        if not cls.s_is_container:
            return RC(False, f'{cls}: may not add a constituent')

        other_cls = other.__class__
        if not self.may_contain_subclasses:
            valid_class = other_cls in cls.s_constituent_classes
        else:
            valid_class = any(issubclass(other_cls, base_cls) for base_cls in cls.s_constituent_classes)
        if not valid_class:
            return RC(False, f'{other.__class__} is not a valid constituent of {cls}')

        if not self.may_contain_self and other == self:
            return RC(False, f'{self} - may not contain itself')

        if not cls.s_is_cumulative and self.is_member(other):
            return RC(False, f'{other} is already contained in {self}')

        return RC_TRUE

    def add_constituent(self, other: BasketLike, qty: float = 1.) -> RC:
        rc = self.check_new_constituent(other)
        if not rc:
            return rc

        basket = self.basket
        existing_qty = basket.get(other, 0.)
        basket[other] = qty + existing_qty
        return RC_TRUE

    def add_basket(self, other: BasketLike, qty: float = 1.) -> RC:
        for member, q in other.basket.items():
            rc = self.add_constituent(member, q * qty)
            if not rc:
                return rc

        return RC_TRUE

    @classmethod
    def is_reachable(cls, basket_level: type[BasketLike]) -> bool:
        constituent_classes = cls.s_constituent_classes
        if basket_level in constituent_classes:
            return True

        for c in constituent_classes:
            if c is not cls and c.is_reachable(basket_level):
                return True

        return False

    @classmethod
    def new_basket(cls) -> BasketLike:
        if cls.s_is_cumulative:
            return Basket()
        else:
            return BasketSet()

    def roots(self) -> BasketLike:
        return self

    def leaves(self) -> BasketLike:
        return self

    def flatten(self, basket_level: type[BasketLike], member_filter: f = None) -> BasketLike:
        res = basket_level.new_basket()
        for member, q in self.basket.items():
            member_class = member.__class__
            if member_class is basket_level:
                if member_filter.eval(member):
                    res.add_constituent(member, q)
            else:
                sub_basket = member.flatten(basket_level, member_filter = member_filter)
                res.add_basket(sub_basket, q)

        return res

    def contents(self, basket_level: type[BasketLike]) -> BasketLike:
        cls = self.__class__
        if basket_level is cls:
            return self.leaves()

        if not cls.is_reachable(basket_level):
            return None

        return self.flatten(basket_level)


class BasketSet(BasketLike, is_base_class = True):
    s_is_container      = True
    s_is_cumulative     = False

class Basket(BasketLike, is_base_class = True):
    s_is_container      = True
    s_is_cumulative     = True


class FinInstrument(BasketLike, may_contain = Self): ...
class FinBasket(Basket, may_contain = FinInstrument): ...
class Trade(BasketLike, may_contain = FinBasket): ...
class Book(BasketLike, may_contain = Trade): ...

class Portfolio(BasketLike, may_contain = (Self, Book)): ...
