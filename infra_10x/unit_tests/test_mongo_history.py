import pytest

from core_10x.testlib.fixtures import with_transactions
from core_10x.testlib.traitable_history_tests import (
    TestTraitableHistory,
    make_clock_freezer,
    test_collection,
    test_store,
)


@pytest.fixture
def clock_freezer(ts_instance):
    """Mongo cannot freeze ``$$NOW``; reuse the shared flowing server_time cut+wait."""
    return make_clock_freezer(ts_instance, freeze=False)
