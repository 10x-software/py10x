import pytest

from core_10x.testlib.fixtures import stub_log_logger
from core_10x.ts_store import TsStore


@pytest.fixture(scope='module',params=[True, False], ids=['hybrid','blob-only'])
def ts_instance(request):
    from infra_10x.duckdb_store import DuckDbStore
    assert not TsStore.s_instances

    orig = DuckDbStore.s_supports_add_column_if_not_exists
    DuckDbStore.s_supports_add_column_if_not_exists = request.param
    yield DuckDbStore.instance()
    DuckDbStore.s_supports_add_column_if_not_exists = orig
    TsStore.s_instances.clear()
