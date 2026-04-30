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
from core_10x.traitable import RT, T, Bundle, Traitable


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


class _PlainTraitable(Traitable):
    pid: str = T(T.ID)


class TestIsBundleDistinguishesPlainTraitable:
    def test_plain_traitable_serialize_class_id_is_none(self):
        assert _PlainTraitable.serialize_class_id() is None

    def test_plain_traitable_serialize_class_id_func_matches_traitable(self):
        """The underlying function for `serialize_class_id` on a non-Bundle
        Traitable IS the Traitable default - this is the property
        ``is_bundle()`` is *meant* to test by-function-identity."""
        assert _PlainTraitable.serialize_class_id.__func__ is Traitable.serialize_class_id.__func__

    @pytest.mark.xfail(
        strict=True,
        reason=(
            'BUG: is_bundle() compares bound classmethods with `is not`, which is '
            'always True for any subclass.  Intended check is on `.__func__`.  '
            'Currently returns True for plain Traitable subclasses too.'
        ),
    )
    def test_plain_traitable_is_not_a_bundle(self):
        assert not _PlainTraitable.is_bundle()


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

        with pytest.raises(AssertionError, match='is not storable'):

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
