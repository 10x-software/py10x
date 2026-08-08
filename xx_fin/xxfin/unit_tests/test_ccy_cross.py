import pytest
from core_10x.rc import RC, RC_TRUE

from xxfin.ccy_cross import CCY_CROSS_TYPE, CcyCross


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