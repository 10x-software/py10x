import pytest
from core_10x.exec_control import GRAPH_ON
from core_10x.testlib.ts_store_isolation import pin_current_ts_stores, unpin_ts_stores
from core_10x.ts_store import TsStore
from py10x_kernel import BTraitableProcessor

from xxfin.pricing_context import PricingContext


@pytest.fixture(autouse=True)
def reset_pricing_context():
    # ``@cache`` memos (Ccy.USD, CcyCross._resolve, FinCalendar.none, …) are cleared by
    # py10x ``test_isolation`` via ``global_cache._clear_all_caches``. Domain process
    # globals that are *not* ``@cache`` still need an explicit reset here.
    yield
    PricingContext.s_current_pc = None


@pytest.fixture(autouse=True)
def graph_on():
    with GRAPH_ON():
        yield


@pytest.fixture(scope='session', autouse=True)
def test_xxfin_main_store():
    from core_10x.environment_variables import EnvVars

    EnvVars.main_ts_store_uri = 'duckdb://localhost/test_xxfin'
    import xxfin.dev_data_helpers.xxfin_stores_and_associations_create as xxfin_stores

    xxfin_stores.named_stores = ({'logical_name': 'mkt_data', 'uri': 'duckdb://localhost/mkt_data'},)
    from xxfin.dev_data_helpers.RUN_ME import run

    with BTraitableProcessor.create_root():
        run()

    from xxfin.xxfin_env_vars import XXFinEnvVars

    XXFinEnvVars.default_pricing_context_name = 'Abu Dhabi 20251010'
    XXFinEnvVars.use_cxxfin = True

    # Survive py10x_core test_isolation: re-publish all open stores (main, mkt_data, …)
    # and main/vault URIs after each test clear. Pin only after run() has opened them.
    pin_current_ts_stores()
    try:
        yield TsStore.instance_from_uri(uri=EnvVars.main_ts_store_uri)
    finally:
        unpin_ts_stores()
