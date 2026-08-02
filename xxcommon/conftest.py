import pytest

@pytest.fixture(scope='module')
def ts_instance():
    from infra_10x.duckdb_store import DuckDbStore

    yield DuckDbStore.instance()
