from datetime import datetime
import itertools
import random

from core_10x.basket import Basket, Basketable, BUCKET_SHAPE, BucketDict
from core_10x.traitable import Traitable, T, RT
from core_10x.trait_filter import f


class FinInstrument(Traitable, Basketable, bucket_shape = BUCKET_SHAPE.DICT):
    name: str       = T(T.ID)
    leaves: dict    = T()

    def price(self):
        return sum(leaf.price() * qty for leaf, qty in self.leaves.items())

    def members_qtys(self):
        return self.leaves.items()

class FinLeaf(FinInstrument):
    def price(self):
        mu = random.randint(1,100)
        return random.gauss(mu = mu, sigma = 10.)

class FiBasket(Basket):
    def base_class_get(self):
        return FinInstrument

    #def value(self, p: float) -> float:
    #    return p * sum(self.members.values())

class Trade(Traitable, Basketable, bucket_shape = BUCKET_SHAPE.DICT):
    name: str           = T(T.ID)
    booked_at: datetime = T()
    book1_name: str     = T()
    book2_name: str     = T()
    basket: FiBasket    = T()

    def members_qtys(self):
        return self.basket.members_qtys()

    def is_member(self, obj) -> bool:
        return self.basket.is_member(obj)

class Book(Traitable, Basketable, bucket_shape = BUCKET_SHAPE.SET):
    name: str                       = T(T.ID)
    customer_book: bool             = T()

    primary_trades: BucketDict      = RT()
    counterparty_trades: BucketDict = RT()

    def primary_trades_get(self) -> BucketDict:
        return BucketDict(data = { trade: 1. for trade in Trade.existing_instances_by_filter(f(book1_name = self.name)) })

    def counterparty_trades_get(self) -> BucketDict:
        return BucketDict(data = { trade: -1. for trade in Trade.existing_instances_by_filter(f(book2_name = self.name)) })

    def members_qtys(self):
        return itertools.chain(self.primary_trades.members_qtys(), self.counterparty_trades.members_qtys())

    def is_member(self, obj) -> bool:
        return self.primary_trades.is_member(obj)

class Portfolio(Traitable, Basketable, bucket_shape = BUCKET_SHAPE.SET):
    name: str               = T(T.ID)

    portfolio_names: list   = T()
    book_names: list        = T()

    portfolios: Basket      = RT()
    books: Basket           = RT()

    def portfolios_get(self):
        basket = Basket(base_class = Portfolio, subclasses_allowed = False)
        for pname in self.portfolio_names:
            basket.add(Portfolio.existing_instance(name = pname))
        return basket

    def books_get(self):
        basket = Basket(base_class = Book, subclasses_allowed = False)
        for bname in self.book_names:
            basket.add(Book.existing_instance(name = bname))
        return basket

    def is_member(self, obj) -> bool:
        return self.portfolios.is_member(obj) or self.books.is_member(obj)

    def members_qtys(self):
        return itertools.chain(self.portfolios.members_qtys(), self.books.members_qtys())

if __name__ == '__main__':
    from core_10x.manual_tests.basketable_hierarchy_test import Portfolio, Book, Trade, FinInstrument, FinLeaf

    l1 = FinLeaf(name = 'Leaf 1')
    l2 = FinLeaf(name = 'Leaf 2')

    f1 = FinInstrument(
        _replace = True,
        name    = 'F1',
        leaves = {l1: 5., l2: -6.}
    )

    f2 = FinInstrument(name = 'F2')
    f3 = FinInstrument(name = 'F3')

    t1 = Trade(_replace = True,
        name        = 'T1',
        book1_name  = 'Book1',
        book2_name  = 'Book2',
        basket      = FiBasket(the_bucket = BucketDict(data = {f1: 10., f2: -2.}))
    )

    t2 = Trade(_replace = True,
        name        = 'T2',
        book1_name  = 'Book3',
        book2_name  = 'Book2',
        basket      = FiBasket(bucket = BucketDict(data = {f3: 4.}))
    )

    b1 = Book(_replace = True, name = 'Book1', customer_book = False)
    b2 = Book(_replace = True, name = 'Book2', customer_book = True)
    b3 = Book(_replace = True, name = 'Book3', customer_book = False)

    p1 = Portfolio(_replace = True, name    = 'P1', book_names = ['Book1'])
    p2 = Portfolio(_replace = True, name    = 'P2', book_names = ['Book2'])

    p = Portfolio(
        _replace = True,
        name    = 'Top',
        portfolio_names = ['P1', 'P2'],
        book_names = ['Book3']
    )

    basket1 = Basket(base_class = Book)
    p.contents(basket1)

    basket2 = Basket(base_class = Trade)
    p.contents(basket2)

    basket3 = Basket(base_class = FinInstrument)
    p.contents(basket3)


    assert p.is_member(b1)
    assert b1.is_member(t1)
    assert t1.is_member(f1)



    # books = p.contents(Book)
    #
    # trades = p.contents(Trade)
    #
    # leaves = p.contents(FinInstrument, leaves = True)
    #
    # r = trades.value(1500.)

