import pytest

from core_10x.ts_store import TsStore


@pytest.fixture(scope='module')
def ts_instance():
    from infra_10x.duckdb_store import DuckDbStore
    yield DuckDbStore.instance()
