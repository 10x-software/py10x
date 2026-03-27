"""Unit tests for TsStore abstract bases. Transaction tests run from testlib against ts_instance (see conftest)."""

import pytest

from core_10x.testlib.fixtures import with_transactions
from core_10x.ts_store import TsCollection, TsStore
from core_10x.ts_union import TsUnion

from core_10x.testlib.ts_store_transaction_tests import TestSaveIfChanged, TestTsStoreTransaction  # collected by pytest
from core_10x.testlib.ts_tests import TestTSStore, ts_setup  # collected by pytest


class TestAbstractBases:
    def test_ts_store_is_abstract(self):
        with pytest.raises(TypeError, match='abstract'):
            # noinspection PyAbstractClass
            TsStore()

    def test_ts_collection_is_abstract(self):
        with pytest.raises(TypeError, match='abstract'):
            # noinspection PyAbstractClass
            TsCollection()

    def test_ts_union_no_stores_returns_no_op_transaction(self):
        union = TsUnion()
        with union.transaction() as tx:
            assert not tx.ended
        assert tx.ended
