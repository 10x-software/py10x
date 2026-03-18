from core_10x.basket import Basket, Basketable, BUCKET_SHAPE, T, RT
from core_10x.trait_filter import f


class FinInstrument(Basketable, bucket_shape = BUCKET_SHAPE.DICT):
    name: str       = T(T.ID)
    leaves: dict    = T()

class FinLeaf(FinInstrument):
    ...

class FinBasket(Basketable):
    member_class: type[Basket] = T(FinInstrument)

    def value(self, p: float) -> float:
        return p * sum(self.members.values())

from datetime import datetime

class Trade(FinBasket, bucket_shape = BUCKET_SHAPE.DICT):
    booked_at: datetime = T()
    book1_name: str     = T()
    book2_name: str     = T()

class Book(Basketable, bucket_shape = BUCKET_SHAPE.SET):
    member_class: type[Basket]  = T(Trade)
    name: str                   = T(T.ID)

    def members_get(self) -> dict:
        primary_trades      = { trade: 1.   for trade in Trade.existing_instances_by_filter(f(book1_name = self.name)) }
        counterparty_trades = { trade: -1.  for trade in Trade.existing_instances_by_filter(f(book2_name = self.name)) }
        return primary_trades | counterparty_trades

class Portfolio(Basketable, bucket_shape = BUCKET_SHAPE.SET):
    name: str               = T(T.ID)

    portfolios: Basket   = T()
    books: Basket        = T()

    def is_member(self, obj: Basket) -> bool:
        return self.portfolios.is_member(obj) or self.books.is_member(obj)

    def items(self):
        return self.ComboIter(self.portfolios.items(), self.books.items())

from core_10x.named_constant import NamedCallable

class FEATURE(NamedCallable):
    A60     = lambda p: p.older_than(60)
    W200    = lambda p: p.weight >= 200

if __name__ == '__main__':
    from core_10x.manual_tests.basket_test import Portfolio, Book, Trade, FinInstrument

    from core_10x.code_samples.person import Person
    from core_10x.xinf import XInf

    all_people = Person.load_many()

    class AGGREGATOR(NamedCallable):
        WEIGHT     = lambda gen: sum(v*q for v, q in gen)

    #b = Basket.simple(Person)
    #b = Basket.by_feature(Person, FEATURE.W200)
    #b = Basket.by_breakpoints(Person, lambda p: p.weight, -XInf, 100, 170, 200, XInf)
    b = Basket.by_range(Person, Person.T.weight, ('underweight', -XInf, 100), ('normal', 170., 180.), ['overweight', 190., XInf])
    b.aggregator_class = AGGREGATOR

    #b = Basket.by_feature(Person, lambda p: p.weight, 190., 200.)
    #b = Basket.by_feature(Person, Person.T.weight, 190., 200.)
    for i, p in enumerate(all_people):
        b.add(p, i)


    #ta = Person.T.weight

    # l1 = FinLeaf(name = 'Leaf 1')
    # l2 = FinLeaf(name = 'Leaf 2')
    #
    # f1 = FinInstrument(
    #     _replace = True,
    #     name    = 'F1',
    #     leaves = {l1: 5., l2: -6.}
    # )
    #
    # f2 = FinInstrument(name = 'F2')
    # f3 = FinInstrument(name = 'F3')
    #
    # t1 = Trade(
    #     book1_name  = 'Book1',
    #     book2_name  = 'Book2',
    #     members     = {f1: 10., f2: -2.}
    #
    # )
    #
    # t2 = Trade(
    #     book1_name  = 'Book3',
    #     book2_name  = 'Book2',
    #     members     = {f3: 4.}
    # )
    #
    # b1 = Book(name = 'Book1')
    # b3 = Book(name = 'Book3')
    # b2 = Book(name = 'Book2')
    #
    # p2 = Portfolio(
    #     _replace = True,
    #     name    = 'P2',
    #     books = BasketSet(member_class = Book, members = {b2})
    # )
    #
    # p1 = Portfolio(
    #     _replace = True,
    #     name    = 'P1',
    #     books = BasketSet(member_class = Book, members = {b1})
    # )
    #
    # p = Portfolio(
    #     _replace = True,
    #     name    = 'Top',
    #     portfolios = BasketSet(member_class = Portfolio, members = {p1}),
    #     books = BasketSet(member_class = Book, members = {b3})
    # )
    #
    # books = p.contents(Book)
    #
    # trades = p.contents(Trade)
    #
    # leaves = p.contents(FinInstrument, leaves = True)
    #
    # r = trades.value(1500.)
    #
