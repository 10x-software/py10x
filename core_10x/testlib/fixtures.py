import sys

import polars as pl
import pytest

from core_10x.environment_variables import EnvVars
from core_10x.logger import LOG
from core_10x.rel_db import RelDb
from core_10x.testlib.strict import need
from core_10x.testlib.stub_logger import stub_log_module_logger
from core_10x.testlib.ts_store_isolation import pin_current_ts_stores, unpin_ts_stores
from core_10x.traitable import Traitable


@pytest.fixture(params=[True, False], ids=['with_transactions', 'without_transactions'])
def with_transactions(request, ts_instance, monkeypatch):
    use_transactions = request.param
    if use_transactions:
        # Only Mongo-standalone lacks transaction support (DuckDB/Ibis report True); under
        # XX_TEST_STRICT a non-replica-set Mongo in CI is a provisioning failure, not a skip.
        need(ts_instance.supports_transactions(), 'store supports transactions (replica-set Mongo, not standalone)')

    monkeypatch.setenv('XX_USE_TS_STORE_TRANSACTIONS', '1' if use_transactions else '0')
    EnvVars.__dict__['use_ts_store_transactions'].fget.clear()
    yield use_transactions


@pytest.fixture
def stub_log_logger(request):
    """Install :class:`StubLogLogger` as the global ``LOGGER`` for synchronous ``LOG.*`` tests.

    Default log level is ``LOG.BRIEF``.  For other levels use indirect parametrization::

        @pytest.mark.parametrize('stub_log_logger', [LOG.VERBOSE.value], indirect=True)
        def test_all_levels(stub_log_logger):
            ...
    """
    level = getattr(request, 'param', LOG.BRIEF.value)
    with stub_log_module_logger(level) as stub:
        yield stub


@pytest.fixture
def temp_duck_db_uri(tmp_path):
    path = (tmp_path / 'test.db').as_posix()
    uri = f'duckdb://{path[0:2]}//{path[3:]}' if sys.platform == 'win32' else f'duckdb:///{path}'
    spec = RelDb.spec_from_uri(uri)
    assert uri == spec.uri()

    RelDb.instance_from_uri(uri).insert('prices', pl.DataFrame({'symbol': ['AAPL', 'MSFT'], 'price': [5, 6]}))

    return uri


@pytest.fixture(scope='module')
def main_test_store():
    """Activate an in-memory DuckDbStore as the main Traitable store and vault.

    Sets ``Env.main_ts_store_uri`` and ``Env.vault_uri`` to in-process
    ``duckdb://`` URIs so vault lookups resolve against an empty vault store
    rather than raising ``OSError`` — resources open without credentials,
    matching a dev environment with no secrets configured.

    The store is **pinned** for the module lifetime so py10x_core ``test_isolation``
    re-publishes it after each test clear (see ``core_10x.testlib.ts_store_isolation``).
    """
    EnvVars.main_ts_store_uri = 'duckdb://localhost/main'
    EnvVars.main_vault_uri = 'duckdb://localhost/vault'
    Traitable.main_store.clear()
    Traitable.vault_store.clear()
    pin_current_ts_stores()
    try:
        yield Traitable.main_store()
    finally:
        unpin_ts_stores()
