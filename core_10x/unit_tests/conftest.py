import pytest
from core_10x.ts_store import TsStore


@pytest.fixture(scope='module')
def ts_instance():
    from core_10x.testlib.test_store import TestStore

    assert not TsStore.s_instances
    yield TestStore.instance()
    TsStore.s_instances.clear()