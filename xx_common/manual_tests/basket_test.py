if __name__ == '__main__':
    from xx_common.basket import Portfolio, Book, Trade, FinBasket, FinInstrument, BasketSet, Basket

    f1 = FinInstrument(name = 'F1')
    f2 = FinInstrument(name = 'F2')
    f3 = FinInstrument(name = 'F3')

    t1 = Trade(
        book1_name  = 'Book1',
        book2_name  = 'Book2',
        members     = {f1: 10., f2: -2.}
    )

    t2 = Trade(
        book1_name  = 'Book3',
        book2_name  = 'Book2',
        members     = {f3: 4.}
    )

    b1 = Book(name = 'Book1')
    b3 = Book(name = 'Book3')
    b2 = Book(name = 'Book2')

    p2 = Portfolio(
        _replace = True,
        name    = 'P2',
        books = BasketSet(member_class = Book, members = {b2})
    )

    p1 = Portfolio(
        _replace = True,
        name    = 'P1',
        books = BasketSet(member_class = Book, members = {b1})
    )

    p = Portfolio(
        _replace = True,
        name    = 'Top',
        portfolios = BasketSet(member_class = Portfolio, members = {p1}),
        books = BasketSet(member_class = Book, members = {b3})
    )

    books = p.contents(Book)

    trades = p.contents(Trade)
