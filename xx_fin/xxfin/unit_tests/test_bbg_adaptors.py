from dataclasses import dataclass

import pytest
from xxcommon.rdate import RDate
from xxfin.bbg_adaptors.bbg_adaptor import BbgAdaptor
from xxfin.bbg_adaptors.fx_spot_fwd_quotable_bbg_adaptors import (
    FXForwardQuotableBbgAdaptor,
    FXSpotQuotableBbgAdaptor,
)
from xxfin.bbg_adaptors.ir_cash_deposit_quotable_bbg_adaptors import IRCashDepositQuotableBbgAdaptor
from xxfin.bbg_adaptors.ir_swap_quotable_bbg_adaptors import IRSwapQuotableBbgAdaptor


@dataclass
class FakeQuotable:
    """Minimal stand-in for a MktQuotable: ticker() only reads mkt_name/tenor/mkt_conventions."""

    mkt_name: str = None
    tenor: RDate = None
    mkt_conventions: object = None


def test_fx_spot_ticker_uses_bbg_mkt_and_suffix():
    assert FXSpotQuotableBbgAdaptor.ticker(FakeQuotable(mkt_name='GBP/USD')) == 'GBPUSD Curncy'
    assert FXSpotQuotableBbgAdaptor.ticker(FakeQuotable(mkt_name='EUR/USD')) == 'EURUSD Curncy'


def test_fx_spot_ticker_unknown_mkt_name_raises():
    with pytest.raises(KeyError):
        FXSpotQuotableBbgAdaptor.ticker(FakeQuotable(mkt_name='XXX/YYY'))


def test_fx_forward_ticker_regular_tenor():
    q = FakeQuotable(mkt_name='GBP/USD', tenor=RDate('3M'))
    assert FXForwardQuotableBbgAdaptor.ticker(q) == 'GBPUSD3M Curncy'


def test_fx_forward_ticker_week_tenor():
    q = FakeQuotable(mkt_name='EUR/USD', tenor=RDate('1W'))
    assert FXForwardQuotableBbgAdaptor.ticker(q) == 'EURUSD1W Curncy'


def test_fx_forward_ticker_overnight_bizday_tenor_becomes_on():
    q = FakeQuotable(mkt_name='GBP/USD', tenor=RDate('1B'), mkt_conventions=object())
    assert FXForwardQuotableBbgAdaptor.ticker(q) == 'GBPUSDON Curncy'


def test_fx_forward_ticker_spot_next_bizday_tenor_becomes_sn():
    q = FakeQuotable(mkt_name='GBP/USD', tenor=RDate('2B'), mkt_conventions=object())
    assert FXForwardQuotableBbgAdaptor.ticker(q) == 'GBPUSDSN Curncy'


def test_ir_cash_deposit_ticker_bizday_tenor_uses_bbg_index():
    q = FakeQuotable(mkt_name='SOFR', tenor=RDate('1B'))
    assert IRCashDepositQuotableBbgAdaptor.ticker(q) == 'SOFRRATE Index'


def test_ir_cash_deposit_ticker_bizday_tenor_requires_count_one():
    q = FakeQuotable(mkt_name='SOFR', tenor=RDate('2B'))
    with pytest.raises(AssertionError):
        IRCashDepositQuotableBbgAdaptor.ticker(q)


def test_ir_cash_deposit_ticker_week_tenor_is_1z():
    q = FakeQuotable(mkt_name='SOFR', tenor=RDate('1W'))
    assert IRCashDepositQuotableBbgAdaptor.ticker(q) == 'USOSFR1Z BGN Curncy'


@pytest.mark.parametrize(
    'months, expected',
    [
        (1, 'USOSFRA BGN Curncy'),
        (2, 'USOSFRB BGN Curncy'),
        (11, 'USOSFRK BGN Curncy'),
        (12, 'USOSFR1 BGN Curncy'),
    ],
)
def test_ir_cash_deposit_ticker_month_tenor_uses_letter_code(months, expected):
    q = FakeQuotable(mkt_name='SOFR', tenor=RDate(f'{months}M'))
    assert IRCashDepositQuotableBbgAdaptor.ticker(q) == expected


def test_ir_cash_deposit_ticker_applies_bbg_cut_when_present():
    # SARON has a 'L' cut inserted between 'BGN' and the ' Curncy' suffix.
    q = FakeQuotable(mkt_name='SARON', tenor=RDate('3M'))
    assert IRCashDepositQuotableBbgAdaptor.ticker(q) == 'SFSNTC BGNL Curncy'


def test_ir_cash_deposit_ticker_no_cut_for_other_markets():
    q = FakeQuotable(mkt_name='ESTR', tenor=RDate('3M'))
    assert IRCashDepositQuotableBbgAdaptor.ticker(q) == 'EESWEC BGN Curncy'


def test_ir_swap_ticker_year_tenor():
    q = FakeQuotable(mkt_name='SOFR', tenor=RDate('5Y'))
    assert IRSwapQuotableBbgAdaptor.ticker(q) == 'USOSFR5 Curncy'


def test_ir_swap_ticker_non_year_tenor_rejected():
    q = FakeQuotable(mkt_name='SOFR', tenor=RDate('6M'))
    with pytest.raises(AssertionError):
        IRSwapQuotableBbgAdaptor.ticker(q)


def test_base_bbg_adaptor_adjust_quote_not_implemented():
    with pytest.raises(NotImplementedError):
        BbgAdaptor.adjust_quote(1.0)
