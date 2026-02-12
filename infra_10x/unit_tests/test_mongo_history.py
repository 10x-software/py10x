from datetime import datetime

import pytest

from core_10x.testlib.traitable_history_tests import TestTraitableHistory, test_collection, test_store

@pytest.fixture
def clock_freezer():
    return datetime