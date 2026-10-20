"""Store-agnostic TsStore transaction tests.

Use ``ts_instance`` from conftest: core_10x → DuckDbStore; infra_10x → MongoStore / PostgresStore.
"""

import pytest
from uuid6 import uuid7

from core_10x.exec_control import INTERACTIVE
from core_10x.rc import RC
from core_10x.testlib.fixtures import with_transactions
from core_10x.testlib.strict import need
from core_10x.trait_definition import T
from core_10x.traitable import Traitable
from core_10x.ts_store import SaveIfChanged


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

            def value_verify(self, t, value) -> bool:
                return RC(value > 0, 'value must be positive')

        tracked = (A, B)
        coll_names = tuple(f'save_if_changed#{cls.__name__.lower()}#{uuid7().hex}' for cls in tracked)
        assert not set(coll_names).intersection(ts_instance.collection_names())

        with ts_instance:
            yield lambda: tuple(cls(i=i, _collection_name=coll_name) for i, (coll_name, cls) in enumerate(zip(coll_names, tracked, strict=False)))

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
        assert a.value == 1  # reverted to the stored value
        assert ctx.tracked_objects() == []  # cleared once reload() succeeds

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

    def test_save_if_changed_parent_isolates_until_save(self, ts_instance, data):
        from core_10x.exec_control import INTERACTIVE

        a, _b = data()
        original = a.value

        # Constructed while `parent` is not current -- the constructor must
        # still enter it itself so get/set_trait_value forwards there.
        parent = INTERACTIVE()
        ctx = SaveIfChanged(auto_save=False, parent=parent)

        with ctx:
            a.value = 42
        # Outside ctx's `with` block, only ts_instance's own ambient scope is
        # current -- the staged edit must be invisible until save().
        assert a.value == original

        rc = ctx.save()
        assert rc
        # a's own cache (ts_instance's scope) doesn't auto-refresh just
        # because some other scope wrote a new value to the store -- reload()
        # (or a fresh load) is how a caller observes it from here.
        assert a.reload()
        assert a.value == 42
        assert a.__class__.collection(a._collection_name).count() == 1

    def test_save_if_changed_parent_already_current_reenters_safely(self, ts_instance, data):
        from core_10x.exec_control import INTERACTIVE

        a, _b = data()
        parent = INTERACTIVE()
        with parent:
            # parent is already current at construction -- SaveIfChanged always
            # enters/exits it itself regardless, and re-entering an
            # already-current BTraitableProcessor is safe (no special-casing
            # needed here).
            ctx = SaveIfChanged(auto_save=False, parent=parent)
            with ctx:
                a.value = 7
            assert a.value == 7  # still current, visible immediately

        rc = ctx.save()
        assert rc
        assert a.__class__.collection(a._collection_name).count() == 1

    def test_save_if_changed_parent_reused_across_sessions(self, ts_instance, data):
        from core_10x.exec_control import INTERACTIVE

        a, b = data()
        parent = INTERACTIVE()
        ctx = SaveIfChanged(auto_save=False, parent=parent)

        with ctx:
            a.value = 1
        ctx.save().throw()
        assert ctx.tracked_objects() == []

        with ctx:
            b.value = 2
        ctx.save().throw()

        assert a.__class__.collection(a._collection_name).count() == 1
        assert b.__class__.collection(b._collection_name).count() == 1

    def test_save_if_changed_no_parent_edits_directly_visible(self, ts_instance, data):
        # No parent passed (defaults to nullcontext()) -- no isolation, matching pre-nesting behavior.
        a, _b = data()
        ctx = SaveIfChanged(auto_save=False)

        with ctx:
            a.value = 5
        assert a.value == 5  # immediately visible, no staging scope involved

        ctx.save().throw()
        assert a.__class__.collection(a._collection_name).count() == 1

    def test_save_if_changed_update_adopts_objects_from_an_accepted_nested_scope(self, ts_instance, data):
        """A nested staging scope exports its *values* into the accumulator's cache, but
        `export_nodes` writes nodes directly rather than through `set_trait_value`, so the
        accumulator never sees the objects. update() is how they are handed over."""

        a, _b = data()

        accumulator = INTERACTIVE()
        tracker = SaveIfChanged(auto_save=False, parent=accumulator)

        with accumulator:
            staging = INTERACTIVE()  # nested in the accumulator, not in the ambient scope
        nested = SaveIfChanged(auto_save=False, parent=staging)
        with nested:
            a.value = 10

        with accumulator:
            staging.export_nodes()  # "accept": values move up one level, objects do not
        assert tracker.tracked_objects() == []

        tracker.update(nested)
        assert tracker.save()
        assert a.reload()
        assert a.value == 10

    def test_save_if_changed_update_skipped_for_a_dropped_nested_scope(self, ts_instance, data):
        """ "Cancel" is simply not exporting and not updating -- the accumulator is untouched."""
        a, _b = data()

        accumulator = INTERACTIVE()
        tracker = SaveIfChanged(auto_save=False, parent=accumulator)

        with accumulator:
            staging = INTERACTIVE()
        nested = SaveIfChanged(auto_save=False, parent=staging)
        with nested:
            a.value = 99

        assert tracker.save()  # nothing exported, nothing adopted
        assert a.__class__.collection(a._collection_name).count() == 0

    def test_save_if_changed_update_is_idempotent(self, ts_instance, data):
        """update() skips objects this tracker already recorded, so folding the same nested
        scope in twice is a no-op."""
        a, b = data()

        ctx = SaveIfChanged(auto_save=False)
        with ctx:
            a.value = 1

        other = SaveIfChanged(auto_save=False)
        with other:
            a.value = 2  # already tracked by ctx
            b.value = 3

        ctx.update(other)
        assert list(ctx._tracked()) == [a, b]

        ctx.update(other)  # idempotent -- update() is pointer-deduped
        assert list(ctx._tracked()) == [a, b]

        ctx.save().throw()
        assert list(ctx._tracked()) == []  # save() clears adopted objects too
        assert a.__class__.collection(a._collection_name).count() == 1
        assert b.__class__.collection(b._collection_name).count() == 1

    def test_save_if_changed_update_dedups_instances_of_the_same_entity(self, ts_instance, data):
        """Dedup is by ID, not by identity. The kernel's own dedup is pointer-based, so two
        instances of one entity are tracked separately -- but they share values and revision,
        so only one of them should ever be saved."""
        a, _b = data()
        same = a.__class__(i=a.i, _collection_name=a._collection_name)
        assert same is not a and same == a

        ctx = SaveIfChanged(auto_save=False)
        with ctx:
            a.value = 1

        other = SaveIfChanged(auto_save=False)
        with other:
            same.value = 2
        assert other.tracked_objects() == [same]

        ctx.update(other)
        assert ctx.tracked_objects() == [a], 'the kernel collapses them by ID on read'
        assert list(ctx._tracked()) == [a]

        ctx.save().throw()
        assert a.__class__.collection(a._collection_name).count() == 1

    def test_save_if_changed_keeps_distinct_objects_that_have_no_ids_yet(self, ts_instance, data):
        """Two objects under construction are distinct pending entities, so ID dedup must
        not collapse them -- both have to survive to be saved. This rests on unshared IDs
        comparing by identity (see test_traitable_id.py::test_unshared_ids_are_distinct)."""

        a, _b = data()
        cls, coll = a.__class__, a._collection_name

        with INTERACTIVE():
            x = cls(_collection_name=coll)
            y = cls(_collection_name=coll)
            assert x != y, 'precondition: unshared objects are distinct entities'

            ctx = SaveIfChanged(auto_save=False)
            with ctx:
                x.value = 1
                y.value = 2

            assert list(ctx._tracked()) == [x, y]
