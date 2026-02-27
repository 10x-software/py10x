"""Unit tests for TsStore abstract bases. Transaction tests run from testlib against ts_instance (see conftest)."""

import pytest

from core_10x.testlib.fixtures import with_transactions
from core_10x.ts_store import TsCollection, TsStore, TsTransaction
from core_10x.ts_union import TsUnion

from core_10x.testlib.ts_store_transaction_tests import TestSaveIfChanged, TestTsStoreTransaction  # collected by pytest
from core_10x.testlib.ts_tests import TestTSStore, ts_setup # collected by pytest



class TestAbstractBases:
    """Abstract base classes cannot be instantiated without implementing abstract methods."""

    def test_ts_transaction_is_abstract(self):
        with pytest.raises(TypeError, match="abstract"):
            TsTransaction()

    def test_ts_union_no_stores_returns_no_op_transaction(self):
        """TsUnion with no stores returns a no-op transaction from _begin_transaction."""
        union = TsUnion()
        tx = union._begin_transaction()
        tx.commit()
        assert tx._ended
        tx._ended = False
        tx.abort()
        assert tx._ended

    def test_ts_store_is_abstract(self):
        with pytest.raises(TypeError, match="abstract"):
            TsStore()

    def test_ts_collection_is_abstract(self):
        with pytest.raises(TypeError, match="abstract"):
            TsCollection()
