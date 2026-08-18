if __name__ == '__main__':

    from xxfin.ccy_cross import Ccy, CcyCross
    from xxcommon.rdate import BIZDAY_ROLL_RULE, RDate

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
        (('EUR', 'GBP'), 'EUR/GBP'),
        (('GBP', 'EUR'), 'EUR/GBP'),

        (('GBP', 'USD'), 'GBP/USD'),
        (('USD', 'GBP'), 'GBP/USD'),

        (('USD', 'JPY'), 'USD/JPY'),
        (('JPY', 'USD'), 'USD/JPY'),

        (('JPY', 'CAD'), 'CAD/JPY'),
        (('CAD', 'JPY'), 'CAD/JPY'),

        (('GBP', 'CHF'), 'GBP/CHF'),
        (('CHF', 'GBP'), 'GBP/CHF'),
    ]

    print('>>> CCY PAIR to NORMAL CROSS <<<')
    for (c1, c2), nc in pair_to_cross:
        print( f'normal cross for {c1, c2} is {nc}')
        assert CcyCross.normal_cross(c1, c2) == nc
        assert CcyCross.is_normal_cross(nc)
        assert CcyCross.normal_cross_from_major_ccys_hierarchy(c1, c2) == nc
        assert CcyCross.normal_cross_from_ccy_hierarchy(c1, c2, CcyCross._major_ccys) == nc

    ## TODO: to run the below tests change Ccy as below:
    # def verified(cls, ccy) -> Ccy:
    #     if type(ccy) is str:
    #         ccy = Ccy(ccy)
    #
    #     elif not isinstance(ccy, Ccy):
    #         raise TypeError(f'Invalid ccy type: {type(ccy)}')
    #
    #     ### if stored and not cls.exists_in_store(ccy.id()):
    #     ###     raise ValueError(f'{ccy} does not exist')
    #
    #     return ccy

    test_ccy_data = (
        dict(name = 'SEK'),
        dict(name = 'NOK'),
        dict(name = 'SGD'),
        dict(name = 'HKD'),
        dict(name = 'KRW'),
        dict(name = 'TWD'),
        dict(name = 'BRL'),
        dict(name = 'ZAR'),
        dict(name = 'INR'),
        dict(name = 'IDR'),

        dict(name = 'XXX'),
        dict(name = 'ZZZ'),
    )
    # ccy_tmpl = dict(
    #         bank_calendar           = 'FD|',
    #         settle_offset           = RDate('2B'),                  ## default
    #         spot_offset             = RDate('2B'),                  ## default
    #         roll_rule               = BIZDAY_ROLL_RULE.FOLLOWING,   ## default
    #         is_deliverable          = False,                         ## default
    #         discounting_mkt_name    = 'SOFR',
    #     )
    # for ccy in test_ccy_data:
    #     ccy.update(ccy_tmpl)

    from xxfin.dev_data_helpers.data_creator import DataCreator
    DataCreator.create(Ccy, test_ccy_data, save = False )

    test_pair_to_cross = [
        (('SEK', 'CHF'), 'CHF/SEK'),
        (('NOK', 'SEK'), 'SEK/NOK'),
        (('KRW', 'SGD'), 'SGD/KRW'),
        (('KRW', 'TWD'), 'KRW/TWD'),
        (('ZAR', 'SGD'), 'SGD/ZAR'),
        (('ZAR', 'BRL'), 'ZAR/BRL'),
    # ]
    # test_unknown_ccy_pair_to_cross = [
        (('KRW', 'XXX'), 'KRW/XXX'),
        (('XXX', 'SEK'), 'SEK/XXX'),
        (('ZAR', 'XXX'), 'ZAR/XXX'),
        (('GBP', 'XXX'), 'GBP/XXX'),
    ]

    print(f'>>> ***TEST*** CCY PAIR to NORMAL CROSS <<<')
    for (c1, c2), nc in test_pair_to_cross:
        print( f'normal cross for {c1, c2} is {nc}')
        assert CcyCross.normal_cross(c1, c2) == nc
        assert CcyCross.is_normal_cross(nc) == True

    print(f'>>> ***TEST*** FULLY UNKNOWN CCY PAIR <<<')
    c1, c2 = ('XXX', 'ZZZ')
    print( f'normal cross for {c1, c2} is {None}')
    assert CcyCross.normal_cross(c1, c2) is None


    test_pair_to_cross_same_hierarchy = [
        (('NOK', 'SEK'), 'SEK/NOK', CcyCross._nordics),
        (('HKD', 'SGD'), 'SGD/HKD', CcyCross._dev_asia),
        (('KRW', 'TWD'), 'KRW/TWD', CcyCross._large_asia),
        (('ZAR', 'BRL'), 'ZAR/BRL', CcyCross._other_EM_good_liq),

    ]

    print(f'>>> ***TEST*** CCY PAIR  ***SAME HIERARCHY*** to NORMAL CROSS <<<')
    for (c1, c2), nc, h in test_pair_to_cross_same_hierarchy:
        print( f'normal cross for {c1, c2} is {nc}')
        assert CcyCross.normal_cross(c1, c2) == nc
        assert CcyCross.is_normal_cross(nc) == True
        assert CcyCross.normal_cross_from_ccy_hierarchy(c1, c2, h) == nc

