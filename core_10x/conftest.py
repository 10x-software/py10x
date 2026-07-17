import pytest

from core_10x.testlib.fixtures import stub_log_logger
from core_10x.ts_store import TsStore

from infra_10x.duckdb_store import DuckDbStore


class TestDuckDbStore(DuckDbStore, resource_name='TEST_DUCK_DB'):
    s_supports_add_column_if_not_exists = False

    def create_index(self, collection_name, name, trait_name, col_trait_dir, **index_args) -> str:
        # Schemaless test store: no online DDL, so payload fields (e.g. history `_at`)
        # cannot be real columns — skip index creation entirely.
        return name


@pytest.fixture(scope='module', params=[True, False], ids=['hybrid', 'blob-only'])
def ts_instance(request):
    assert not TsStore.s_instances

    yield DuckDbStore.instance() if request.param else TestDuckDbStore.instance()
    TsStore.s_instances.clear()
