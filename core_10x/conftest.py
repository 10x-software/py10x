import pytest

from core_10x.testlib.fixtures import stub_log_logger
from core_10x.ts_store import TsStore


@pytest.fixture(scope='module')
def ts_instance():
    from infra_10x.duckdb_store import DuckDbStore

    assert not TsStore.s_instances
    yield DuckDbStore.instance()
    TsStore.s_instances.clear()
