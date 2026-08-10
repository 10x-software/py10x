from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from core_10x.py_class import PyClass
from core_10x.trait_filter import f
from core_10x.traitable import Bundle, T

if TYPE_CHECKING:
    from datetime import date

    from xxfin.mkt_quotable import SingleMktQuote


class MktDataConnector(Bundle):
    provider_name: str = T(T.ID)

    def quote(self, md_date: date, ticker: str) -> float:
        raise NotImplementedError

    @classmethod
    def connector(cls, provider_name: str) -> MktDataConnector:
        matches = cls.load_many(f(provider_name=provider_name))
        assert len(matches) == 1, f'{provider_name}: expected exactly one {cls.__name__}, found {len(matches)}'
        return matches[0]


class MktDataAdaptor:
    s_connector_class = MktDataConnector
    s_provider_name = None

    def __init_subclass__(cls, provider_name=None, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        # Intermediate/abstract adaptor classes (e.g. MktDataAdaptorSingleQuote) legitimately have
        # no provider_name of their own; only a concrete class actually calling connector() needs
        # one, so that's enforced there (lazily), not here at class-definition time.
        if provider_name is not None:
            cls.s_provider_name = provider_name

    @classmethod
    def ticker(cls, quotable: SingleMktQuote) -> str:
        raise NotImplementedError

    @classmethod
    def fill(cls, quotable: SingleMktQuote) -> SingleMktQuote:
        raise NotImplementedError

    @classmethod
    def connector(cls) -> MktDataConnector:
        assert cls.s_provider_name is not None, f'{cls}: provider_name must be specified'
        return cls.s_connector_class.connector(cls.s_provider_name)

    @classmethod
    @contextmanager
    def provider_context(cls, provider_name):
        orig_pn = cls.s_provider_name
        cls.s_provider_name = provider_name
        try:
            yield
        finally:
            cls.s_provider_name = orig_pn

    @staticmethod
    def adaptor(quotable_class, provider_name):
        return PyClass.find_related_class(quotable_class, class_name_suffix=f'{provider_name.title()}Adaptor',topic=f'{provider_name.lower()}_adaptors')


class MktDataAdaptorSingleQuote(MktDataAdaptor):
    @classmethod
    def get_quote(cls, md_date: date, ticker: str):
        raise NotImplementedError

    @classmethod
    def fill(cls, quotable: SingleMktQuote) -> SingleMktQuote:
        md_date = quotable.md_date
        ticker = cls.ticker(quotable)
        quotable.quote = cls.get_quote(md_date, ticker)
        return quotable
