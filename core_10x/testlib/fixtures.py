import sys

import polars as pl
import pytest

from core_10x.environment_variables import EnvVars
from core_10x.logger import LOG
from core_10x.rel_db import RelDb
from core_10x.testlib.stub_logger import stub_log_module_logger
from core_10x.traitable import Traitable
from core_10x.ts_store import TsStore  # used in teardown


@pytest.fixture(params=[True, False], ids=['with_transactions', 'without_transactions'])
def with_transactions(request, ts_instance, monkeypatch):
    use_transactions = request.param
    if use_transactions and not ts_instance.supports_transactions():
        pytest.skip('Store does not support transactions')

    monkeypatch.setenv('XX_USE_TS_STORE_TRANSACTIONS', '1' if use_transactions else '0')
    object.__getattribute__(EnvVars, 'use_ts_store_transactions').fget.clear()
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
    path = (tmp_path / "test.db").as_posix()
    uri = f"duckdb://{path[0:2]}//{path[3:]}" if sys.platform == 'win32' else f"duckdb:///{path}"
    spec = RelDb.spec_from_uri(uri)
    assert uri == spec.uri()

    RelDb.instance_from_uri(uri).insert('prices', pl.DataFrame({'symbol': ['AAPL', 'MSFT'], 'price': [5,6]}))

    return uri


def _clear_main_store_caches():
    """Clear cached main-store-related properties so the next access re-evaluates."""
    object.__getattribute__(EnvVars, 'main_ts_store_uri').fget.clear()
    object.__getattribute__(EnvVars, 'main_vault_uri').fget.clear()
    object.__getattribute__(EnvVars, 'vault_uri').fget.clear()
    # main_store / vault_store are @staticmethod @cache — unwrap via __func__
    object.__getattribute__(Traitable, 'main_store').__func__.clear()
    object.__getattribute__(Traitable, 'vault_store').__func__.clear()


@pytest.fixture(scope='module')
def main_test_store():
    """Activate an in-memory DuckDbStore as the main Traitable store and vault.

    Sets ``XX_MAIN_TS_STORE_URI`` and ``XX_VAULT_URI`` to in-process
    ``duckdb://`` URIs so vault lookups resolve against an empty vault store
    rather than raising ``OSError`` — resources open without credentials,
    matching a dev environment with no secrets configured.
    Stores and caches are torn down automatically at module end.
    """
    _clear_main_store_caches()

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv('XX_MAIN_TS_STORE_URI', 'duckdb://localhost/main')
        mp.setenv('XX_MAIN_VAULT_URI',    'duckdb://localhost/vault')
        mp.setenv('XX_VAULT_URI',         'duckdb://localhost/vault')
        yield Traitable.main_store()

    _clear_main_store_caches()
    TsStore.s_instances.clear()
