"""Store-agnostic TsStore transaction tests.

Use ``ts_instance`` from conftest: core_10x → DuckDbStore; infra_10x → MongoStore / PostgresStore.
"""

import pytest
from uuid6 import uuid7

from core_10x.rc import RC
from core_10x.testlib.fixtures import with_transactions
from core_10x.testlib.strict import need
from core_10x.trait_definition import T
from core_10x.traitable import Traitable
from core_10x.ts_store import SaveIfChanged
from xxcommon.conftest import ts_instance


class TestTsStoreTransaction:
    """Transaction semantics: commit applies changes, abort discards. Runs against ts_instance from conftest."""

    @pytest.fixture(autouse=True)
    def _skip_if_store_does_not_support_transactions(self, ts_instance):
        """Skip this class when the store lacks transactions (Mongo standalone) - fail under strict."""
        need(ts_instance.supports_transactions(), 'store supports transactions (replica-set Mongo, not standalone)')

    @pytest.fixture
    def store(self, ts_instance):
        return ts_instance

    @pytest.fixture
    def coll_name(self):
        return f'ts_store_tx_test#{uuid7().hex}'

    @pytest.fixture
    def coll(self, store, coll_name):
        from core_10x.trait_definition import T
        from core_10x.traitable import Traitable

        class _Pad(Traitable, custom_collection=True, keep_history=False):
            pad: int = T()

        c = store.collection(coll_name, _Pad.s_dir)  # writable schema; raw dict payloads OK
        yield c
        if coll_name in store.collection_names():
            store.delete_collection(coll_name)

    def test_transaction_yields_tx_with_commit_abort(self, store):
        with store.transaction() as tx:
            assert hasattr(tx, 'commit') and hasattr(tx, 'abort')
            assert not tx.ended

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
        with pytest.raises(RuntimeError, match='rollback'), store.transaction():
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
    def data(self, ts_instance):

        class A(Traitable, custom_collection=True):
            i: int = T(T.ID)
            value: int = T()

        class B(Traitable, custom_collection=True):
            i: int = T(T.ID)
            value: int = T()

            def value_verify(self,t,value) -> bool:
                return RC(value>0, "value must be positive")

        tracked = (A,B)
        coll_names = tuple(f'save_if_changed#{cls.__name__.lower()}#{uuid7().hex}' for cls in tracked)
        assert not set(coll_names).intersection(ts_instance.collection_names())

        with ts_instance:
            yield lambda: tuple(cls(i=i, _collection_name=coll_name) for i, (coll_name,cls) in enumerate(zip(coll_names,tracked)))

        for coll_name in coll_names:
            ts_instance.delete_collection(coll_name)

    def test_save_if_changed_filters_by_classes(self, data, with_transactions):  # noqa: F811
        a, b = data()

        with SaveIfChanged([a.__class__]) as tracker:
            a.value = 10
            b.value = 20
            assert tracker.tracked_objects() == [a, b]

        assert a.__class__.collection(a._collection_name).count() == 1
        assert b.__class__.collection(b._collection_name).count() == 0
        assert tracker.tracked_objects() == []


        a.delete()
        assert a.__class__.collection(a._collection_name).count() == 0

        with pytest.raises(RuntimeError, match='must be positive'):
            with SaveIfChanged() as tracker:
                a.value = 20
                b.value = -1
            assert tracker.tracked_objects() == [a, b]

        assert a.__class__.collection(a._collection_name).count() == int(not with_transactions)
        assert b.__class__.collection(b._collection_name).count() == 0

    def test_save_if_changed_requires_storable_classes(self):
        class NotStorable:
            @classmethod
            def is_storable(cls):
                return False

        with pytest.raises(RuntimeError, match='SaveIfChanged must be storable'), SaveIfChanged([NotStorable]):
            pass

    def test_save_if_changed_auto_save_false_defers_until_explicit_save(self, ts_instance, data):
        a, _b = data()

        ctx = SaveIfChanged(auto_save=False)

        with ctx:
            a.value = 10
        # Exiting the `with` block does not save -- auto_save is False.
        assert a.__class__.collection(a._collection_name).count() == 0
        assert ctx.tracked_objects() == [a]

        rc = ctx.save()
        assert rc
        assert a.__class__.collection(a._collection_name).count() == 1
        assert ctx.tracked_objects() == []  # cleared once save() succeeds

    def test_save_if_changed_reused_instance_tracks_only_new_edits_after_save(self, ts_instance, data):
        a, b = data()

        ctx = SaveIfChanged(auto_save=False)
        with ctx:
            a.value = 10
        assert ctx.tracked_objects() == [a]
        ctx.save().throw()
        assert ctx.tracked_objects() == []
        assert a.__class__.collection(a._collection_name).count() == 1

        with ctx:
            b.value = 20
        assert ctx.tracked_objects() == [b]
        ctx.save().throw()
        assert ctx.tracked_objects() == []

        assert b.__class__.collection(b._collection_name).count() == 1


    def test_save_if_changed_reload_reverts_and_clears(self, ts_instance, data):
        a, _b = data()

        a.value = 1
        a.save().throw()

        ctx = SaveIfChanged(auto_save=False)
        with ctx:
            a.value = 99
        assert ctx.tracked_objects() == [a]

        ok = ctx.reload()
        assert ok
        assert a.value == 1        # reverted to the stored value
        assert ctx.tracked_objects() == []   # cleared once reload() succeeds

    def test_save_if_changed_failed_save_keeps_tracked_objects(self, ts_instance, data):
        a, b = data()

        ctx = SaveIfChanged(auto_save=False)

        with ctx:
            a.value = 10
            b.value = -1

        rc = ctx.save()
        assert not rc
        # A failed save must not clear -- the caller needs to inspect/retry.
        assert set(ctx.tracked_objects()) == {a, b}
        ctx.clear()

