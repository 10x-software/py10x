import pytest
from core_10x.rc import RC, RC_TRUE
from xxfin.ccy_cross import CCY_CROSS_TYPE, Ccy, CcyCross


class TestCcyCross:
    def test_ccy_cross(self):
        CcyCross(base_ccy = 'CHF', quote_ccy = 'CAD')

class TestCcyCrossResolve:
    def test_same_ccy(self):
        cross_type1, usd_cross1, cross_type2, usd_cross2  = CcyCross.resolve(cross = 'GBP/GBP')
        assert cross_type1 == CCY_CROSS_TYPE.NONE
        assert cross_type2 == CCY_CROSS_TYPE.NONE
        assert usd_cross1 is None
        assert usd_cross2 is None

    def test_amer_quote(self):
        amer_ccys = ('GBP', 'EUR', 'AUD', 'NZD')

        for ccy in amer_ccys:
            cross_type1, usd_cross1, cross_type2, usd_cross2  = CcyCross.resolve(cross = f'USD/{ccy}')
            assert cross_type1 == CCY_CROSS_TYPE.INVERTED
            assert cross_type2 == CCY_CROSS_TYPE.NONE
            assert usd_cross1 == CcyCross(cross = f'{ccy}/USD')
            assert usd_cross2 is None

        for ccy in amer_ccys:
            cross_type1, usd_cross1, cross_type2, usd_cross2  = CcyCross.resolve(cross = f'{ccy}/USD')
            assert cross_type1 == CCY_CROSS_TYPE.NORMAL
            assert cross_type2 == CCY_CROSS_TYPE.NONE
            assert usd_cross1 == CcyCross(cross = f'{ccy}/USD')
            assert usd_cross2 is None

    def test_usd_european_quoted(self):
        ccys = ('CHF', 'CAD', 'JPY', )

        for ccy in ccys:
            cross_type1, usd_cross1, cross_type2, usd_cross2  = CcyCross.resolve(cross = f'{ccy}/USD')
            assert cross_type1 == CCY_CROSS_TYPE.INVERTED
            assert cross_type2 == CCY_CROSS_TYPE.NONE
            assert usd_cross1 == CcyCross(cross = f'USD/{ccy}')
            assert usd_cross2 is None

        for ccy in ccys:
            cross_type1, usd_cross1, cross_type2, usd_cross2  = CcyCross.resolve(cross = f'USD/{ccy}')
            assert cross_type1 == CCY_CROSS_TYPE.NORMAL
            assert cross_type2 == CCY_CROSS_TYPE.NONE
            assert usd_cross1 == CcyCross(cross = f'USD/{ccy}')
            assert usd_cross2 is None

    def test_non_usd_crosses(self):
        cross_type1, usd_cross1, cross_type2, usd_cross2 = CcyCross.resolve(cross = 'GBP/EUR')
        assert cross_type1 == CCY_CROSS_TYPE.NORMAL
        assert cross_type2 == CCY_CROSS_TYPE.INVERTED
        assert usd_cross1 == CcyCross(cross = 'GBP/USD')
        assert usd_cross2 == CcyCross(cross = 'EUR/USD')

        cross_type1, usd_cross1, cross_type2, usd_cross2 = CcyCross.resolve(cross = 'EUR/GBP')
        assert cross_type1 == CCY_CROSS_TYPE.NORMAL
        assert cross_type2 == CCY_CROSS_TYPE.INVERTED
        assert usd_cross1 == CcyCross(cross = 'EUR/USD')
        assert usd_cross2 == CcyCross(cross = 'GBP/USD')

        cross_type1, usd_cross1, cross_type2, usd_cross2 = CcyCross.resolve(cross = 'CHF/CAD')
        assert cross_type1 == CCY_CROSS_TYPE.INVERTED
        assert cross_type2 == CCY_CROSS_TYPE.NORMAL
        assert usd_cross1 == CcyCross(cross = 'USD/CHF')
        assert usd_cross2 == CcyCross(cross = 'USD/CAD')

    def test_verify(self):
        assert CcyCross(cross = 'USD/CHF').verify(cross = 'USD/CAD') == RC_TRUE
        assert CcyCross(cross = 'USD/CHF').verify(cross = 'USD/USD') == RC_TRUE
        assert CcyCross(cross = 'USD/CHF').verify(base_ccy = 'USD', quote_ccy = 'CAD') == RC_TRUE

        assert CcyCross(cross = 'USD/CHF').verify(cross = 'USD/AED') == RC(False, "Instance does not exist: <class 'xxfin.ccy.Ccy'>({'name': 'AED'})")
        assert CcyCross(cross = 'USD/CHF').verify(base_ccy = 'XXX', quote_ccy = 'YYY') == RC(False, "Instance does not exist: <class 'xxfin.ccy.Ccy'>({'name': 'XXX'})")

    def test_deliverable(self):
        assert CcyCross(cross = 'GBP/EUR').is_deliverable
        Ccy('EUR').is_deliverable = False
        assert not CcyCross(cross = 'GBP/EUR').is_deliverable

    def test_delivery_ccy(self):
        assert CcyCross(cross = 'GBP/EUR').delivery_ccy is None
        Ccy('EUR').is_deliverable = False
        assert CcyCross(cross='GBP/EUR').delivery_ccy == Ccy('GBP')
        Ccy('GBP').is_deliverable = False
        assert CcyCross(cross='GBP/EUR').delivery_ccy is None
        Ccy('EUR').is_deliverable = True
        assert CcyCross(cross='GBP/EUR').delivery_ccy == Ccy('EUR')

    def test_same_ccy_cross(self):
        assert not CcyCross.is_same_ccy_cross(cross = 'GBP/EUR')
        assert CcyCross.is_same_ccy_cross(cross = 'GBP/GBP')

        with pytest.raises(AssertionError, match = 'Invalid cross GBP, must consist of 2 currencies'):
            assert CcyCross.is_same_ccy_cross(cross = 'GBP')
        with pytest.raises(ValueError, match = 'Instance does not exist.*XXX'):
            assert CcyCross.is_same_ccy_cross(cross = 'XXX/GBP')

    def test_invert_cross(self):
        assert CcyCross.invert_cross(cross='GBP/EUR') == 'EUR/GBP'
        assert CcyCross.invert_cross(cross='CHF/CHF') == 'CHF/CHF'

    def test_is_dollar_cross(self):
        assert not CcyCross.is_dollar_cross('GBP', 'EUR')
        assert CcyCross.is_dollar_cross('GBP', 'USD')
        assert CcyCross.is_dollar_cross('USD', 'GBP')
        assert CcyCross.is_dollar_cross('USD', 'USD')

    def test_dollar_cross(self):
        assert CcyCross.dollar_cross('GBP') == CcyCross(cross='GBP/USD')
        assert CcyCross.dollar_cross('CAD') == CcyCross(cross='USD/CAD')
        assert CcyCross.dollar_cross('USD') is None

    def test_dollar_cross_pair(self):
        assert CcyCross.dollar_cross_pair('GBP', 'EUR') == (CcyCross(cross='GBP/USD'), CcyCross(cross='EUR/USD'))
        assert CcyCross.dollar_cross_pair('EUR', 'GBP') == (CcyCross(cross='EUR/USD'), CcyCross(cross='GBP/USD'))

        assert CcyCross.dollar_cross_pair('GBP', 'CAD') == (CcyCross(cross='GBP/USD'), CcyCross(cross='USD/CAD'))
        assert CcyCross.dollar_cross_pair('CAD', 'GBP') == (CcyCross(cross='GBP/USD'), CcyCross(cross='USD/CAD'))

        assert CcyCross.dollar_cross_pair('JPY', 'CAD') == (CcyCross(cross='USD/JPY'), CcyCross(cross='USD/CAD'))
        assert CcyCross.dollar_cross_pair('CAD', 'JPY') == (CcyCross(cross='USD/CAD'), CcyCross(cross='USD/JPY'))

        assert CcyCross.dollar_cross_pair('GBP', 'USD') == (CcyCross(cross='GBP/USD'), )
        assert CcyCross.dollar_cross_pair('USD', 'JPY') == (CcyCross(cross='USD/JPY'), )

        assert CcyCross.dollar_cross_pair('USD', 'USD') == ()
        assert CcyCross.dollar_cross_pair('CHF', 'CHF') == ()
        assert CcyCross.dollar_cross_pair('EUR', 'EUR') == ()

    ## TODO: currently runs on already setup major ccys; expand to non-major ccys
    def test_normal_cross_from_ccy_hierarchys(self):
        pair_to_cross = [
            (('EUR', 'EUR'), 'EUR/EUR'),

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

        for (c1, c2), nc in pair_to_cross:
            assert CcyCross.normal_cross(c1, c2) == nc
            assert CcyCross.is_normal_cross(nc)
            assert CcyCross.normal_cross_from_major_ccys_hierarchy(c1, c2) == nc
            assert CcyCross.normal_cross_from_ccy_hierarchy(c1, c2, CcyCross._major_ccys) == nc


    def test_normal_cross_for_mock_ccys(self):
        ...
    '''
    ## TODO: mock the Ccy.verified(ccy) by removing check exists_in_store():
        # def verified(cls, ccy) -> Ccy:
        #     if type(ccy) is str:
        #         ccy = Ccy(ccy)
        #     elif not isinstance(ccy, Ccy):
        #         raise TypeError(f'Invalid ccy type: {type(ccy)}')
        #     ### if not cls.exists_in_store(ccy.id()):
        #     ###     raise ValueError(f'{ccy} does not exist')
        #     return ccy


        test_ccy_data = (
            dict(name='SEK'),
            dict(name='NOK'),
            dict(name='SGD'),
            dict(name='HKD'),
            dict(name='KRW'),
            dict(name='TWD'),
            dict(name='BRL'),
            dict(name='ZAR'),
            dict(name='INR'),
            dict(name='IDR'),
            dict(name='XXX'),
            dict(name='ZZZ'),
        )
        # ccy_tmpl = dict(
        #     bank_calendar       = 'FD|',
        #     settle_offset       = RDate('2B'),  ## default
        #     spot_offset         = RDate('2B'),  ## default
        #     roll_rule           = BIZDAY_ROLL_RULE.FOLLOWING,  ## default
        #     is_deliverable      = False,  ## default
        #     discounting_mkt_name='SOFR',
        # )
        # for ccy in test_ccy_data:
        #     ccy.update(ccy_tmpl)

        from xxfin.dev_data_helpers.data_creator import DataCreator
        DataCreator.create(Ccy, test_ccy_data, save = False)

        test_pair_to_cross = [
            (('SEK', 'CHF'), 'CHF/SEK'),
            (('NOK', 'SEK'), 'SEK/NOK'),
            (('KRW', 'SGD'), 'SGD/KRW'),
            (('KRW', 'TWD'), 'KRW/TWD'),
            (('ZAR', 'SGD'), 'SGD/ZAR'),
            (('ZAR', 'BRL'), 'ZAR/BRL'),

            (('KRW', 'XXX'), 'KRW/XXX'),
            (('XXX', 'SEK'), 'SEK/XXX'),
            (('ZAR', 'XXX'), 'ZAR/XXX'),
            (('GBP', 'XXX'), 'GBP/XXX'),
        ]

        for (c1, c2), nc in test_pair_to_cross:
            print(f'normal cross for {c1, c2} is {nc}')
            assert CcyCross.normal_cross(c1, c2) == nc
            assert CcyCross.is_normal_cross(nc) == True

        c1, c2 = ('XXX', 'ZZZ')
        assert CcyCross.normal_cross(c1, c2) is None

        test_pair_to_cross_same_hierarchy = [
            (('NOK', 'SEK'), 'SEK/NOK', CcyCross._nordics),
            (('HKD', 'SGD'), 'SGD/HKD', CcyCross._dev_asia),
            (('KRW', 'TWD'), 'KRW/TWD', CcyCross._large_asia),
            (('ZAR', 'BRL'), 'ZAR/BRL', CcyCross._other_EM_good_liq),

        ]

        for (c1, c2), nc, h in test_pair_to_cross_same_hierarchy:
            assert CcyCross.normal_cross(c1, c2) == nc
            assert CcyCross.is_normal_cross(nc) == True
            assert CcyCross.normal_cross_from_ccy_hierarchy(c1, c2, h) == nc
    '''
