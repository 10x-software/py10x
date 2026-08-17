if __name__ == '__main__':

    from xxfin.ccy_cross import Ccy, CcyCross

    base_ccy  = Ccy('GBP')
    quote_ccy = Ccy('EUR')
    quote_ccy.is_deliverable = False
    cc = CcyCross(base_ccy = base_ccy, quote_ccy = quote_ccy)
    print(f'cross = {cc.cross}')
    print(f'is {base_ccy} deliverable = {base_ccy.is_deliverable}')
    print(f'is {quote_ccy} deliverable = {quote_ccy.is_deliverable}')
    print(f'is {cc} deliverable = {cc.is_deliverable}')
    print(f'is {cc} same ccy cross  {CcyCross.is_same_ccy_cross(cc.cross)}')
    print(f'for {cc} inverted is  {CcyCross.invert_cross(cc.cross)}')
    ccys = ['USD', 'EUR', 'GBP', 'CAD', 'CHF', 'JPY']
    for ccy in ccys:
        print(f'{ccy}: a dollar cross {CcyCross.dollar_cross(ccy)}')
        for ccy2 in ccys:
            print(f'{ccy}, {ccy2}: a dollar cross pair {CcyCross.dollar_cross_pair(ccy, ccy2)}')

    ccy = 'EUR'
    ccy2 = 'CAD'
    print(f'{ccy}, {ccy2}: resolve info {CcyCross.resolve(base_ccy=ccy, quote_ccy=ccy2)}')
    print(f'{ccy2}, {ccy}: resolve info {CcyCross.resolve(base_ccy=ccy2, quote_ccy=ccy)}')


    pair_to_cross = [
        (('EUR', 'GBP'), ('EUR/GBP')),
        (('GBP', 'EUR'), ('EUR/GBP')),

        (('GBP', 'USD'), ('GBP/USD')),
        (('USD', 'GBP'), ('GBP/USD')),

        (('USD', 'JPY'), ('USD/JPY')),
        (('JPY', 'USD'), ('USD/JPY')),

        (('JPY', 'CAD'), ('CAD/JPY')),
        (('CAD', 'JPY'), ('CAD/JPY')),

        (('GBP', 'CHF'), ('GBP/CHF')),
        (('CHF', 'GBP'), ('GBP/CHF')),
    ]

    print('>>> CCY PAIR to NORMAL CROSS <<<')
    for (c1, c2), nc in pair_to_cross:
        print( f'normal cross for {c1, c2} is {nc}')
        assert CcyCross.normal_cross(c1, c2) == nc
        assert CcyCross.is_normal_cross(nc)
        assert CcyCross.normal_cross_from_major_ccys_hierarchy(c1, c2) == nc
        assert CcyCross.normal_cross_from_ccy_hierarchy(c1, c2, CcyCross._major_ccys) == nc


