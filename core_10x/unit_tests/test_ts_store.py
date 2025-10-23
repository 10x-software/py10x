import pytest
from core_10x.testlib.ts_tests import *


@pytest.fixture(scope='session')
def ts_instance():
    from core_10x.testlib.test_store import TestStore

    return TestStore.instance()
