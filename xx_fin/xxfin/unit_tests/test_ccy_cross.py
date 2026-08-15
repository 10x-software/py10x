import pytest
from core_10x.rc import RC, RC_TRUE
from xxfin.ccy_cross import CCY_CROSS_TYPE, CcyCross, Ccy


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

        assert CcyCross(cross = 'USD/CHF').verify(cross = 'USD/AED') == RC(False, 'AED does not exist')
        assert CcyCross(cross = 'USD/CHF').verify(base_ccy = 'XXX', quote_ccy = 'YYY') == RC(False, 'XXX does not exist')

    def test_deliverable(self):
        assert CcyCross(cross = 'GBP/EUR').is_deliverable == True
        Ccy('EUR').is_deliverable = False
        assert CcyCross(cross = 'GBP/EUR').is_deliverable == False

    def test_delivery_ccy(self):
        assert CcyCross(cross = 'GBP/EUR').delivery_ccy is None
        Ccy('EUR').is_deliverable = False
        assert CcyCross(cross='GBP/EUR').delivery_ccy == Ccy('GBP')
        Ccy('GBP').is_deliverable = False
        assert CcyCross(cross='GBP/EUR').delivery_ccy is None
        Ccy('EUR').is_deliverable = True
        assert CcyCross(cross='GBP/EUR').delivery_ccy == Ccy('EUR')

    def test_same_ccy_cross(self):
        assert CcyCross.is_same_ccy_cross(cross = 'GBP/EUR') == False
        assert CcyCross.is_same_ccy_cross(cross = 'GBP/GBP') == True

        with pytest.raises(AssertionError, match = 'Invalid cross GBP, must consist of 2 currencies'):
            assert CcyCross.is_same_ccy_cross(cross = 'GBP')
        with pytest.raises(ValueError, match = 'XXX does not exist'):
            assert CcyCross.is_same_ccy_cross(cross = 'XXX/GBP')

    def test_invert_cross(self):
        assert CcyCross.invert_cross(cross='GBP/EUR') == 'EUR/GBP'
        assert CcyCross.invert_cross(cross='CHF/CHF') == 'CHF/CHF'

    def test_is_dollar_cross(self):
        assert CcyCross.is_dollar_cross('GBP', 'EUR') == False
        assert CcyCross.is_dollar_cross('GBP', 'USD') == True
        assert CcyCross.is_dollar_cross('USD', 'GBP') == True
        assert CcyCross.is_dollar_cross('USD', 'USD') == True

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