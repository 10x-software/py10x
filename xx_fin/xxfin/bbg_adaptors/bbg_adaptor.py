from __future__ import annotations

from decimal import Decimal

from xxfin.mkt_adaptor import MktDataAdaptorSingleQuote


class BbgAdaptor(MktDataAdaptorSingleQuote, provider_name='BBG'):
    # provider_name='BBG' is inherited unchanged by every subclass (ir/fx/commodity alike), so
    # they all share one connector via MktDataAdaptor.connector() without needing an override here.
    SUFFIX = None

    @classmethod
    def adjust_quote(cls, raw_value: float) -> float:
        raise NotImplementedError

    @classmethod
    def get_quote(cls, md_date, ticker):
        raw_value = cls.connector().quote(md_date, ticker)
        return cls.adjust_quote(raw_value)


class BbgAdaptorIRFX(BbgAdaptor):
    SUFFIX = ' Curncy'


class BbgAdaptorIR(BbgAdaptorIRFX):
    BBG_MKT = {
        'SOFR': 'USOSFR',
        'SONIA': 'BPSWS',
        'ESTR': 'EESWE',
        'SARON': 'SFSNT',
        'TONA': 'JYSO',
        'CORRA': 'CDSO',
    }

    @classmethod
    def adjust_quote(cls, raw_value: float) -> float:
        return float(Decimal(str(raw_value)) / 100)


class BbgAdaptorFX(BbgAdaptorIRFX):
    BBG_MKT = {
        'GBP/USD': 'GBPUSD',
        'EUR/USD': 'EURUSD',
        'USD/CAD': 'USDCAD',
        'USD/CHF': 'USDCHF',
        'USD/JPY': 'USDJPY',
    }

    @classmethod
    def adjust_quote(cls, raw_value: float) -> float:
        return raw_value
