from datetime import datetime
import time

import pytest

from core_10x.testlib.traitable_history_tests import TestTraitableHistory, test_collection, test_store

@pytest.fixture
def clock_freezer():
    class Freezer:
        @staticmethod
        def utcnow():
            time.sleep(0.001)
            return datetime.utcnow()
    return Freezer
