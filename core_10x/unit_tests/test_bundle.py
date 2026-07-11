"""Unit tests for the Bundle facility (core_10x.traitable.Bundle).

A `Bundle` is a `Traitable` whose subclasses all share the bundle base's
collection.  The first concrete subclass becomes the *bundle base*
(``s_bundle_base``); every further subclass is a *member* registered on the
base and gets ``cls.collection`` bound to the base's ``collection``.

Because all members live in one collection, the serialized record carries a
class id that lets the framework rebuild the right concrete subclass.
``Bundle`` supports two flavors, selected by the ``members_known`` keyword
on the bundle base:

* ``members_known=False`` (default): members are *not* tracked.  Each member
  serializes its full ``PackageRefactoring`` class id and deserialization
  goes through the package refactoring registry.
* ``members_known=True``: members register themselves on the base under
  ``cls.__name__``.  Each member serializes just its short class name and
  deserialization is a dict lookup on the base.
"""

from __future__ import annotations

import pytest

from core_10x.exec_control import CACHE_ONLY
from core_10x.traitable import RT, T, Bundle, BundleHistory, Traitable


# ---------------------------------------------------------------------------
# Bundle with members_known=True - short-name registry
# ---------------------------------------------------------------------------


class Animals(Bundle, members_known=True):
    """Bundle base with an explicit member registry."""

    name: str = T(T.ID)


class Dog(Animals):
    breed: str = T()


class Cat(Animals):
    indoor: bool = T()


class TestBundleMembersKnown:
    def test_base_class_is_set_to_first_subclass(self):
        assert Animals.s_bundle_base is Animals
        assert Dog.s_bundle_base is Animals
        assert Cat.s_bundle_base is Animals

    def test_members_registered_by_short_name(self):
        members = Animals.s_bundle_members
        assert isinstance(members, dict)
        assert members['Dog'] is Dog
        assert members['Cat'] is Cat

    def test_serialize_class_id_returns_short_name(self):
        assert Dog.serialize_class_id() == 'Dog'
        assert Cat.serialize_class_id() == 'Cat'

    def test_deserialize_class_id_round_trip(self):
        assert Animals.deserialize_class_id(Dog.serialize_class_id()) is Dog
        assert Animals.deserialize_class_id(Cat.serialize_class_id()) is Cat

    def test_deserialize_unknown_member_raises(self):
        with pytest.raises(ValueError, match='unknown bundle member'):
            Animals.deserialize_class_id('Hamster')

    def test_deserialize_empty_id_raises(self):
        with pytest.raises(ValueError, match='missing serialized class ID'):
            Animals.deserialize_class_id('')

    def test_members_share_base_collection(self):
        # `cls.collection = base.collection` in __init_subclass__ binds the
        # members' `collection` attribute to the *base*'s bound classmethod.
        # The descriptors are therefore the same callable object.
        assert Dog.collection == Animals.collection
        assert Cat.collection == Animals.collection

    def test_is_bundle_for_base_and_members(self):
        # is_bundle() must be True for any class that overrode
        # serialize_class_id, which Bundle does.
        assert Animals.is_bundle()
        assert Dog.is_bundle()
        assert Cat.is_bundle()

    def test_serialize_class_id_func_differs_from_traitable(self):
        """Underlying function for `serialize_class_id` is the Bundle override,
        not the Traitable default.  This is the property `is_bundle()` is
        *intended* to detect."""
        assert Animals.serialize_class_id.__func__ is not Traitable.serialize_class_id.__func__
        assert Dog.serialize_class_id.__func__ is not Traitable.serialize_class_id.__func__


# ---------------------------------------------------------------------------
# Bundle with members_known=False (default) - full class-id form
# ---------------------------------------------------------------------------


class Vehicles(Bundle):
    """Bundle base without a member registry (default)."""

    plate: str = T(T.ID)


class Car(Vehicles):
    doors: int = T()


class TestBundleMembersUnknown:
    def test_base_class_is_set(self):
        assert Vehicles.s_bundle_base is Vehicles
        assert Car.s_bundle_base is Vehicles

    def test_no_member_registry(self):
        assert Vehicles.s_bundle_members is None

    def test_serialize_class_id_is_package_refactoring_id(self):
        from core_10x.package_refactoring import PackageRefactoring

        sid = Car.serialize_class_id()
        assert isinstance(sid, str)
        assert sid == PackageRefactoring.find_class_id(Car)

    def test_deserialize_class_id_resolves_via_package_refactoring(self):
        sid = Car.serialize_class_id()
        assert Vehicles.deserialize_class_id(sid) is Car

    def test_deserialize_empty_id_raises(self):
        with pytest.raises(ValueError, match='missing serialized class ID'):
            Vehicles.deserialize_class_id('')

    def test_is_bundle_true_even_without_registry(self):
        assert Vehicles.is_bundle()
        assert Car.is_bundle()


# ---------------------------------------------------------------------------
# Bundle vs. plain Traitable
# ---------------------------------------------------------------------------





class TestIsBundleDistinguishesPlainTraitable:
    class _PlainTraitable(Traitable):
        pid: str = T(T.ID)

    def test_plain_traitable_serialize_class_id_is_none(self):
        assert self._PlainTraitable.serialize_class_id() is None

    def test_plain_traitable_serialize_class_id_func_matches_traitable(self):
        """The underlying function for `serialize_class_id` on a non-Bundle
        Traitable IS the Traitable default - this is the property
        ``is_bundle()`` is *meant* to test by-function-identity."""
        assert self._PlainTraitable.serialize_class_id.__func__ is Traitable.serialize_class_id.__func__

    def test_plain_traitable_is_not_a_bundle(self):
        assert not self._PlainTraitable.is_bundle()


# ---------------------------------------------------------------------------
# Storable requirement for direct (non-base) members
# ---------------------------------------------------------------------------


class TestBundleStorableRequirement:
    def test_non_storable_member_rejected(self):
        """A member that is not storable (no stored ID trait) is rejected by
        Bundle.__init_subclass__.

        We use an *abstract* bundle base (no ID traits, hence not storable
        itself).  The base passes the first-subclass branch and is therefore
        not checked.  A second subclass that also lacks ID traits goes
        through the storable assertion.
        """

        class _AbstractBundle(Bundle, members_known=True):
            pass  # no ID trait -> not storable

        # Base itself is allowed (storable check only applies to subsequent
        # subclasses) and the registry is initialized.
        assert _AbstractBundle.s_bundle_base is _AbstractBundle
        assert _AbstractBundle.s_bundle_members == {}

        with pytest.raises(RuntimeError, match='is not storable'):

            class _NonStorableMember(_AbstractBundle):
                pass  # still no ID trait -> not storable

    def test_storable_member_accepted(self):
        """A member with a stored ID trait passes the storable check and registers."""

        class _AbstractBundle2(Bundle, members_known=True):
            pass

        class _StorableMember(_AbstractBundle2):
            mid: str = T(T.ID)

        assert _AbstractBundle2.s_bundle_members['_StorableMember'] is _StorableMember


# ---------------------------------------------------------------------------
# Non-storable bundle base + storable members - history classes must STILL
# share a single history collection (lazily created on the bundle base).
# ---------------------------------------------------------------------------


class AbstractAnimals(Bundle, members_known=True):
    """Bundle base without ID traits - not storable on its own."""


class Wolf(AbstractAnimals):
    name: str = T(T.ID)
    howl_pitch: int = T()


class Bear(AbstractAnimals):
    name: str = T(T.ID)
    den: str = T()


class TestBundleHistoryWithNonStorableBase:
    """When the bundle base is non-storable but the members are storable, the
    members' history classes must still share a common ``<Base>#history``
    collection.  The fix is to lazily create the bundle base's history class
    when the first storable member is encountered (so subsequent siblings can
    register against it as Bundle members)."""

    def test_lazy_base_history_class_created(self):
        # The non-storable bundle base now has a history class lazily attached.
        base_hist = AbstractAnimals.s_history_class
        assert isinstance(base_hist, type)
        assert issubclass(base_hist, BundleHistory)
        assert base_hist.__name__ == 'AbstractAnimals#history'
        assert base_hist.s_traitable_class is AbstractAnimals
        assert base_hist.s_bundle_base is base_hist

    def test_member_history_classes_are_bundle_members_of_lazy_base(self):
        base_hist = AbstractAnimals.s_history_class
        wolf_hist = Wolf.s_history_class
        bear_hist = Bear.s_history_class

        assert wolf_hist.s_bundle_base is base_hist
        assert bear_hist.s_bundle_base is base_hist

        # AbstractAnimals is members_known=True, so its lazy history class is too.
        assert base_hist.s_bundle_members is not None
        assert base_hist.s_bundle_members['Wolf#history'] is wolf_hist
        assert base_hist.s_bundle_members['Bear#history'] is bear_hist

    def test_member_history_classes_share_collection_method(self):
        # Bundle.__init_subclass__ rebinds member's collection -> base's.
        # Once the lazy base history class is in place, all member histories
        # resolve to the same collection callable.
        base_hist = AbstractAnimals.s_history_class
        assert Wolf.s_history_class.collection == base_hist.collection
        assert Bear.s_history_class.collection == base_hist.collection

    def test_lazy_base_storage_helper_promotes_non_storable_base(self, bundle_history_store):
        """The non-storable bundle base also gets a real (storable) storage
        helper at the same time as its lazy history class - so that members
        sharing `cls.collection = base.collection` actually route to a real
        collection instead of `NotStorableHelper.collection() == None`."""
        # Base is not storable on its own (no T.ID), but its cached helper was
        # promoted - so member-side `collection()` returns a real collection
        # (its base's), not `None`.
        assert not AbstractAnimals.is_storable()
        assert Wolf.collection() is not None
        assert Bear.collection() is not None
        assert Wolf.collection() is Bear.collection()

    def test_storage_helper_rederived_from_history_class_after_cache_clear(self, bundle_history_store):
        """Helper cache is ephemeral; a real ``s_history_class`` must re-derive WithHistory.

        AsOfContext (and similar) nulls ``s_storage_helper_cached`` on all Traitable
        subclasses. The non-storable bundle base still has a history class from member
        registration — resolution must follow that, not ``is_storable()`` alone.
        """
        from datetime import datetime

        from core_10x.traitable import AsOfContext, StorableHelperWithHistory

        assert AbstractAnimals.s_history_class  # promotion installed a real history class
        with AsOfContext(as_of_time=datetime.utcnow()):
            pass  # exit clears every subclass helper cache

        assert AbstractAnimals.s_storage_helper_cached is None
        assert isinstance(AbstractAnimals.s_storage_helper, StorableHelperWithHistory)
        assert Wolf.collection() is not None
        assert Wolf.collection() is Bear.collection()

    def test_member_main_record_routes_to_base_collection(self, bundle_history_store):
        """Saving a storable member of a NON-storable bundle base actually
        persists to a real collection (the base's) - the whole point of
        promoting the base's storage helper.  Without the lazy promotion, the
        base's helper would be ``NotStorableHelper`` and the save would
        silently no-op."""
        w = Wolf(name='wolf_main', _replace=True)
        w.howl_pitch = 7
        w.save().throw()

        b = Bear(name='bear_main', _replace=True)
        b.den = 'oak_hollow'
        b.save().throw()

        # Both members landed in the SAME (base's) collection.
        base_coll = AbstractAnimals.collection()
        assert base_coll is Wolf.collection()
        assert base_coll is Bear.collection()

        docs = {doc['_id']: doc for doc in base_coll.find()}
        assert w.id().value in docs
        assert b.id().value in docs
        assert docs[w.id().value]['_cls'] == 'Wolf'
        assert docs[w.id().value]['howl_pitch'] == 7
        assert docs[b.id().value]['_cls'] == 'Bear'
        assert docs[b.id().value]['den'] == 'oak_hollow'

    def test_member_history_records_share_lazy_base_history_collection(self, bundle_history_store):
        """History records for storable members of a non-storable bundle base
        all land in the ONE lazily-created ``<Base>#history`` collection,
        mirroring the storable-base case."""
        w = Wolf(name='wolf_hist', _replace=True)
        w.howl_pitch = 3
        w.save().throw()

        b = Bear(name='bear_hist', _replace=True)
        b.den = 'cave'
        b.save().throw()

        base_hist_coll = AbstractAnimals.s_history_class.collection()
        assert Wolf.s_history_class.collection() is base_hist_coll
        assert Bear.s_history_class.collection() is base_hist_coll

        cls_values = {doc['_cls'] for doc in base_hist_coll.find()}
        assert {'Wolf#history', 'Bear#history'} <= cls_values

    def test_member_history_query_filters_by_class_with_lazy_base(self, bundle_history_store):
        """``Wolf.history()`` returns only Wolf history records even though
        Wolves and Bears live in the same shared (lazily-created) history
        collection on the non-storable base."""
        w = Wolf(name='wolf_filter', _replace=True)
        w.howl_pitch = 5
        w.save().throw()

        b = Bear(name='bear_filter', _replace=True)
        b.den = 'pine'
        b.save().throw()

        wolf_history = list(Wolf.history())
        bear_history = list(Bear.history())

        assert all(h['_cls'] == 'Wolf#history' for h in wolf_history)
        assert all(h['_cls'] == 'Bear#history' for h in bear_history)

        wolf_ids = {h['_traitable_id'] for h in wolf_history}
        bear_ids = {h['_traitable_id'] for h in bear_history}
        assert w.id().value in wolf_ids
        assert b.id().value in bear_ids
        assert b.id().value not in wolf_ids
        assert w.id().value not in bear_ids


# ---------------------------------------------------------------------------
# Round-trip behavior with CACHE_ONLY context
# ---------------------------------------------------------------------------


class TestBundleInstancesRoundTrip:
    """End-to-end check that bundle members can be instantiated and that the
    polymorphic class id maps back to the right subclass."""

    def test_instantiate_members_in_cache_only(self):
        with CACHE_ONLY():
            d = Dog(name='rex_bundle', _replace=True)
            d.breed = 'lab'
            c = Cat(name='whiskers_bundle', _replace=True)
            c.indoor = True

            assert isinstance(d, Dog)
            assert isinstance(c, Cat)
            assert type(d).serialize_class_id() == 'Dog'
            assert type(c).serialize_class_id() == 'Cat'

    def test_class_id_lookup_via_base(self):
        """Given only the base class and a serialized id, recover the concrete class."""
        with CACHE_ONLY():
            d = Dog(name='rex_bundle2', _replace=True)
            sid = type(d).serialize_class_id()
            recovered_cls = Animals.deserialize_class_id(sid)
            assert recovered_cls is Dog


# ---------------------------------------------------------------------------
# Bundle + TraitableHistory
# ---------------------------------------------------------------------------
#
# Bundle members share the bundle base's `collection` (by design).  History
# classes mirror the same structure: `<Base>#history` is itself a Bundle
# base, and every `<Member>#history` is a Bundle member of `<Base>#history`,
# so all member histories share one history collection (`<Base>#history`).
# Class-based filtering on read time (in `StorableHelperWithHistory._find`)
# ensures that querying via a member's history class returns only that
# member's records, even though they all live in the shared collection.
# ---------------------------------------------------------------------------


class TestBundleHistoryStaticWiring:
    """Static (no-store) checks of how Bundle interacts with TraitableHistory."""

    def test_member_main_collection_is_shared_with_base(self):
        # Bundle.__init_subclass__ rebinds cls.collection -> base.collection.
        assert Dog.collection == Animals.collection
        assert Cat.collection == Animals.collection

    def test_each_member_has_its_own_history_class(self):
        # Per-class history classes are still distinct objects: each carries
        # its own `s_traitable_class` and serializes a distinct `_cls`.
        assert Dog.s_history_class is not Animals.s_history_class
        assert Cat.s_history_class is not Animals.s_history_class
        assert Dog.s_history_class is not Cat.s_history_class

        assert Dog.s_history_class.__name__ == 'Dog#history'
        assert Cat.s_history_class.__name__ == 'Cat#history'
        assert Animals.s_history_class.__name__ == 'Animals#history'

        assert Dog.s_history_class.s_traitable_class is Dog
        assert Cat.s_history_class.s_traitable_class is Cat
        assert Animals.s_history_class.s_traitable_class is Animals

    def test_member_history_class_resolves_its_own_class_id(self):
        """Each history class resolves to its own ``<Member>#history`` class
        id, which is what the framework writes to ``_cls`` on history records
        and uses for class-based filtering on reads."""
        from core_10x.package_refactoring import PackageRefactoring

        assert PackageRefactoring.find_class_id(Dog.s_history_class).endswith('/Dog#history')
        assert PackageRefactoring.find_class_id(Cat.s_history_class).endswith('/Cat#history')
        assert PackageRefactoring.find_class_id(Animals.s_history_class).endswith('/Animals#history')

    def test_history_classes_form_a_bundle_mirroring_main_classes(self):
        """The history-class hierarchy mirrors the main-class hierarchy:
        ``<Base>#history`` is the bundle base for histories, and every
        ``<Member>#history`` is a Bundle member of ``<Base>#history``."""
        animals_hist = Animals.s_history_class
        dog_hist = Dog.s_history_class
        cat_hist = Cat.s_history_class

        assert issubclass(animals_hist, Bundle)
        assert issubclass(dog_hist, Bundle)
        assert issubclass(cat_hist, Bundle)

        assert animals_hist.s_bundle_base is animals_hist
        assert dog_hist.s_bundle_base is animals_hist
        assert cat_hist.s_bundle_base is animals_hist

        # Animals is a `members_known=True` bundle, so its history is too.
        assert animals_hist.s_bundle_members is not None
        assert animals_hist.s_bundle_members['Dog#history'] is dog_hist
        assert animals_hist.s_bundle_members['Cat#history'] is cat_hist

        # Members share the base's collection (by Bundle's normal contract).
        assert dog_hist.collection == animals_hist.collection
        assert cat_hist.collection == animals_hist.collection


# ---------------------------------------------------------------------------
# Empirical save/history tests against the in-memory DuckDbStore
# ---------------------------------------------------------------------------


@pytest.fixture
def bundle_history_store(ts_instance):
    """Store fixture mirroring the one in core_10x.testlib.traitable_history_tests.

    NOTE: ``ts_instance`` is module-scoped, so every test in this file shares
    the same DuckDbStore.  The fixture clears collections between tests, but
    cannot reset class-level ``s_storage_helper_cached`` attributes, which is
    where the runtime bug is sensitive to ordering.  We pick test scenarios
    that do not depend on a virgin helper cache.
    """
    store = ts_instance
    store.username = 'test_user'
    store.begin_using()
    yield store
    for cn in store.collection_names():
        store.delete_collection(cn)
    store.end_using()


class TestBundleHistoryBehavior:
    """Live save/history checks against a DuckDbStore."""

    def test_main_record_routes_to_base_collection(self, bundle_history_store):
        """Main records go to the bundle base's collection - this is the
        whole point of Bundle."""
        d = Dog(name='dog_main', _replace=True)
        d.breed = 'lab'
        d.save().throw()

        base_coll = Animals.collection()
        assert base_coll.count() >= 1
        loaded = next(doc for doc in base_coll.find() if doc['_id'] == d.id().value)
        assert loaded['_cls'] == 'Dog'
        assert loaded['breed'] == 'lab'

    def test_history_records_share_the_base_history_collection(self, bundle_history_store):
        """All members' history records land in the ONE shared
        ``<Base>#history`` collection - the history-class hierarchy mirrors
        the bundle's main-class hierarchy."""
        d = Dog(name='dog_share', _replace=True)
        d.breed = 'beagle'
        d.save().throw()

        c = Cat(name='cat_share', _replace=True)
        c.indoor = True
        c.save().throw()

        animals_hist_coll = Animals.s_history_class.collection()
        dog_hist_coll = Dog.s_history_class.collection()
        cat_hist_coll = Cat.s_history_class.collection()

        # All three resolve to the same shared collection.
        assert dog_hist_coll is animals_hist_coll
        assert cat_hist_coll is animals_hist_coll

        cls_values = {doc['_cls'] for doc in animals_hist_coll.find()}
        assert {'Dog#history', 'Cat#history'} <= cls_values

    def test_member_history_query_filters_by_class(self, bundle_history_store):
        """``Cat.history()`` returns only Cat records even though Cats and
        Dogs live in the same shared history collection - the framework
        filters by ``_cls`` in ``StorableHelperWithHistory._find``."""
        d = Dog(name='dog_filter', _replace=True)
        d.breed = 'lab'
        d.save().throw()

        c = Cat(name='cat_filter', _replace=True)
        c.indoor = True
        c.save().throw()

        cat_history = list(Cat.history())
        dog_history = list(Dog.history())

        assert all(h['_cls'] == 'Cat#history' for h in cat_history)
        assert all(h['_cls'] == 'Dog#history' for h in dog_history)

        cat_ids = {h['_traitable_id'] for h in cat_history}
        dog_ids = {h['_traitable_id'] for h in dog_history}
        assert c.id().value in cat_ids
        assert d.id().value in dog_ids
        assert d.id().value not in cat_ids
        assert c.id().value not in dog_ids
