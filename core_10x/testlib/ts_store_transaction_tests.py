"""Store-agnostic TsStore transaction tests. Use ts_instance fixture from conftest (core_10x → TestStore, infra_10x → MongoStore)."""
from uuid import uuid4

import pytest


class TestTsStoreTransaction:
    """Transaction semantics: commit applies changes, abort discards. Runs against ts_instance from conftest."""

    @pytest.fixture(autouse=True)
    def _skip_if_store_does_not_support_transactions(self, ts_instance):
        """Skip this test class when the store does not support transactions (e.g. MongoDB standalone)."""
        if not getattr(ts_instance, 'supports_transactions', lambda: True)():
            pytest.skip(
                "Store does not support transactions "
                "(e.g. MongoDB standalone; needs replica set or mongos)"
            )

    @pytest.fixture
    def store(self, ts_instance):
        return ts_instance

    @pytest.fixture
    def coll_name(self):
        return f'ts_store_tx_test#{uuid4().hex}'

    @pytest.fixture
    def coll(self, store, coll_name):
        c = store.collection(coll_name)
        yield c
        if coll_name in store.collection_names():
            store.delete_collection(coll_name)

    def test_transaction_yields_tx_with_commit_abort(self, store):
        with store.transaction() as tx:
            assert hasattr(tx, 'commit') and hasattr(tx, 'abort')
            assert not tx._ended

    def test_commit_applies_pending_writes(self, store, coll):
        coll.save_new({'_id': 'a', '_rev': 0}, overwrite=False)
        assert coll.count() == 1
        with store.transaction() as tx:
            coll.save_new({'_id': 'b', '_rev': 0}, overwrite=False)
            assert coll.count() == 2
            tx.commit()
        assert coll.count() == 2
        assert coll.id_exists('b')

    def test_abort_discards_pending_writes(self, store, coll):
        coll.save_new({'_id': 'a', '_rev': 0}, overwrite=False)
        with store.transaction() as tx:
            coll.save_new({'_id': 'b', '_rev': 0}, overwrite=False)
            tx.abort()
        assert coll.count() == 1
        assert not coll.id_exists('b')

    def test_exception_triggers_abort(self, store, coll):
        coll.save_new({'_id': 'a', '_rev': 0}, overwrite=False)
        with pytest.raises(RuntimeError, match='rollback'):
            with store.transaction():
                coll.save_new({'_id': 'd', '_rev': 0}, overwrite=False)
                raise RuntimeError('rollback')
        assert coll.count() == 1
        assert not coll.id_exists('d')

    def test_manual_commit_before_exit(self, store, coll):
        with store.transaction() as tx:
            coll.save_new({'_id': 'x', '_rev': 0}, overwrite=False)
            tx.commit()
        assert coll.count() == 1
        assert coll.id_exists('x')

    def test_double_commit_no_op(self, store, coll):
        with store.transaction() as tx:
            coll.save_new({'_id': 'y', '_rev': 0}, overwrite=False)
            tx.commit()
            tx.commit()
        assert coll.count() == 1

    def test_transaction_sees_own_pending_in_find(self, store, coll):
        with store.transaction() as tx:
            coll.save_new({'_id': 'z', '_rev': 0}, overwrite=False)
            docs = list(coll.find())
            assert len(docs) == 1
            assert docs[0]['_id'] == 'z'
            tx.commit()
        assert coll.count() == 1

    def test_transaction_delete_pending(self, store, coll):
        coll.save_new({'_id': 'del', '_rev': 0}, overwrite=False)
        with store.transaction() as tx:
            assert coll.delete('del')
            assert not coll.id_exists('del')
            tx.commit()
        assert coll.count() == 0
        assert not coll.id_exists('del')

    def test_transaction_delete_then_abort_restores_visibility(self, store, coll):
        coll.save_new({'_id': 'del2', '_rev': 0}, overwrite=False)
        with store.transaction() as tx:
            coll.delete('del2')
            assert not coll.id_exists('del2')
            tx.abort()
        assert coll.id_exists('del2')
        assert coll.count() == 1
