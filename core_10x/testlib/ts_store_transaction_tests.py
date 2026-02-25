"""Store-agnostic TsStore transaction tests. Use ts_instance fixture from conftest (core_10x → TestStore, infra_10x → MongoStore)."""
from uuid import uuid4

import pytest

from core_10x.rc import RC
from core_10x.testlib.fixtures import with_transactions
from core_10x.trait_definition import T
from core_10x.traitable import Traitable
from core_10x.ts_store import SaveIfChanged


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


class TestSaveIfChanged:
    @pytest.fixture
    def coll_names(self,ts_instance):
        coll_names = tuple(f'save_if_changed#{x}#{uuid4().hex}' for x in ('a','b'))
        assert not set(coll_names).intersection(ts_instance.collection_names())
        yield coll_names
        for coll_name in coll_names:
            ts_instance.delete_collection(coll_name)

    def test_save_if_changed_filters_by_classes(self, ts_instance, coll_names, with_transactions):  # noqa: F811

        coll_a_name, coll_b_name = coll_names
        class TrackedA(Traitable, custom_collection=True):
            i: int = T(T.ID)
            value: int = T()

        class TrackedB(Traitable, custom_collection=True):
            i: int = T(T.ID)
            value: int = T()

            def save(self,save_references=True):
                return RC(False,'boom')

        with ts_instance:
            a = TrackedA(i=1, _collection_name=coll_a_name)
            b = TrackedB(i=2, _collection_name=coll_b_name)
            with SaveIfChanged([TrackedA]) as tracker:
                a.value = 10
                b.value = 20
                assert tracker.tracked_objects() == [a,b]

            assert ts_instance.collection(coll_a_name).count() == 1
            assert ts_instance.collection(coll_b_name).count() == 0

            a.delete()
            assert ts_instance.collection(coll_a_name).count() == 0

            with pytest.raises(RuntimeError,match='boom'):
                with SaveIfChanged() as tracker:
                    a.value = 20
                    b.value = 30
                assert tracker.tracked_objects() == [a,b]

            assert ts_instance.collection(coll_a_name).count() == int(not with_transactions)
            assert ts_instance.collection(coll_b_name).count() == 0

    def test_save_if_changed_requires_storable_classes(self):
        class NotStorable:
            @classmethod
            def is_storable(cls):
                return False

        with pytest.raises(RuntimeError, match='SaveIfChanged must be storable'):
            with SaveIfChanged([NotStorable]):
                pass
