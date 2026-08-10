from __future__ import annotations

from datetime import date

from core_10x.traitable import T

from xxfin.mkt_adaptor import MktDataConnector

class DevBbgConnector(MktDataConnector):
    """In-memory ticker/date -> px_last lookup, for dev/test fixtures. No DB/network involved."""

    records: dict = T({})  # {(ticker, date): px_last}

    def quote(self, md_date: date, ticker: str) -> float:
        return self.records.get((ticker, md_date), float('nan'))

class LiveBbgConnector(MktDataConnector):
    """Real Bloomberg connector via xbbg (optional `bbg` extra). Import is lazy so this module
    stays importable without xbbg/blpapi installed."""

    def quote(self, md_date: date, ticker: str) -> float:
        from xbbg import blp

        df = blp.bdh(ticker, 'PX_LAST', start_date=md_date, end_date=md_date)
        return float(df.iloc[0, 0]) if not df.empty else float('nan')
