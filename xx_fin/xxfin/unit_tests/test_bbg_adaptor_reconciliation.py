"""Reconciles the BBG adaptor framework end-to-end against the hand-curated dev fixtures, using
DevBbgConnector (provider 'BBG_DEV', in-memory fake data) and, when the optional `bbg` extra (xbbg +
blpapi) is installed, LiveBbgConnector (provider 'BBG', with blp.bdh monkeypatched to serve the exact
same fake data instead of hitting a real Bloomberg session - xbbg's own mock_engine still requires a
working engine/session, so this uses the same technique xbbg's own offline tests use: patching the
top-level blp function directly). Both connectors are set up once at session start by
xxfin/dev_data_helpers/bbg_dev_connector_create.py.

Walks every (MktQuotablesScope, PricingContext, quotable_class, stub) combination for provider
'XX_DEV' and, for each one that already has an XX_DEV quote, fills a fresh quotable (a brand new,
never-saved instance under a random provider_name) via the real BBG adaptor's ticker()/fill() and
asserts it exactly matches the XX_DEV value. Runs twice, parametrized over 'dev'/'live' - the 'live'
run is skipped when xbbg/blpapi aren't installed, and hard-fails instead under XX_TEST_STRICT=1
(core_10x.testlib.strict.need), matching py10x's own convention for provisioning-dependent tests.

Combinations with no XX_DEV quote, or whose quotable class has no matching BBG adaptor, are
tracked and checked against the pinned EXPECTED_* sets below rather than silently skipped.
"""

from datetime import date

import numpy as np
import pytest
import uuid6
from core_10x.testlib.strict import need
from core_10x.trait_filter import f
from core_10x.xnone import XNone
from xxfin.bbg_adaptors.bbg_adaptor import BbgAdaptor
from xxfin.fx_spot_fwd_quotable import FXForwardQuotable, FXSpotQuotable
from xxfin.ir_cash_deposit_quotable import IRCashDepositQuotable
from xxfin.ir_swap_quotable import IRSwapQuotable
from xxfin.mkt_adaptor import MktDataAdaptor, MktDataConnector
from xxfin.mkt_quotables_scope import MktQuotablesScope
from xxfin.pricing_context import PricingContext

EXPECTED_MISSING = {
    ('SARON', date(2025, 5, 30)),
    ('SARON', date(2025, 10, 10)),
    ('ESTR', date(2025, 5, 30)),
    ('ESTR', date(2025, 10, 10)),
    ('TONA', date(2025, 5, 30)),
    ('CORRA', date(2025, 5, 30)),
    ('GBP/USD', date(2025, 5, 30)),
    ('EUR/USD', date(2025, 5, 30)),
    ('USD/CHF', date(2025, 5, 30)),
    ('USD/CAD', date(2025, 5, 30)),
    ('USD/JPY', date(2025, 5, 30)),
}
EXPECTED_EXTRAS = {('2025-10-10', IRSwapQuotable): 2}

def _bbg_dependencies_available() -> bool:
    try:
        import blpapi
        import xbbg
        return True
    except ImportError:
        return False

@pytest.fixture(params=['dev', 'live'])
def bbg_connector_mode(request, monkeypatch):
    if request.param == 'live':
        need(_bbg_dependencies_available(), 'xbbg/blpapi not installed (optional `bbg` extra)')
        import pandas as pd
        from xbbg import blp

        def _bdh(tickers, flds=None, start_date=None, end_date=None, **kwargs):
            ticker = tickers if isinstance(tickers, str) else tickers[0]
            value = MktDataConnector.connector('BBG_DEV').records.get((ticker, start_date), float('nan'))
            return pd.DataFrame({'PX_LAST': [value]})

        monkeypatch.setattr(blp, 'bdh', _bdh)
        yield
    else:
        with BbgAdaptor.provider_context('BBG_DEV'):
            yield


def test_bbg_adaptor_reproduces_dev_data_quotes(bbg_connector_mode):
    pcs = PricingContext.load_many(f(mkt_data_provider_name='XX_DEV'))
    assert len(pcs) > 1

    quotable_scopes = MktQuotablesScope.load_many()
    assert len(quotable_scopes) > 1

    found_classes = set()
    test_provider_name = uuid6.uuid7().hex
    for mqs in quotable_scopes:
        for pc in pcs:
            for q_cls, q_stub in mqs.quotable_class_and_stubs_generator(pc.md_date):
                found_classes.add(q_cls)
                q_id_traits = {'mkt_name': mqs.mkt_name, **q_stub, **pc.md_basis}
                dev_q = q_cls.existing_instance(**q_id_traits, _throw=False)
                if not dev_q:
                    assert (mqs.mkt_name, pc.md_date) in EXPECTED_MISSING
                    continue
                assert not np.isnan(dev_q.quote)

                test_q = q_cls(**q_id_traits | {'provider_name': test_provider_name})
                assert test_q.get_revision() == 0
                assert test_q.quote is XNone

                adaptor = MktDataAdaptor.adaptor(q_cls, provider_name='BBG')
                assert adaptor, f'missing adaptor class for {q_cls}'

                adaptor.fill(test_q)
                assert test_q.quote == dev_q.quote, f'{dev_q}.quote={dev_q.quote!r}!={test_q.quote!r}'
                test_q.save().throw()

    assert found_classes == {IRSwapQuotable, IRCashDepositQuotable, FXForwardQuotable, FXSpotQuotable}

    for cls in found_classes:
        # FX spots have several EXPECTED_MISSING dates; floor is below IR/FX-forward totals.
        assert cls.collection().count(f(provider_name=test_provider_name)) > 3

        for pc in pcs:
            md_date = pc.md_date
            n = cls.collection().count(f(provider_name=test_provider_name, md_date=md_date, trait_dir=cls.s_dir))
            m = cls.collection().count(f(provider_name='XX_DEV', md_date=md_date, trait_dir=cls.s_dir))
            assert n + EXPECTED_EXTRAS.get((str(md_date), cls), 0) == m
            if m > 0:
                assert n > 0
