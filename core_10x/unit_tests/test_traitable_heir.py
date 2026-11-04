"""Unit tests for core_10x.traitable_heir.TraitableHeir.

A trait of a ``TraitableHeir`` subclass with neither a custom getter nor a default is an *heir trait*:
unless set on the heir itself, its value comes from the trait of the same name on ``_grantor``.
Unset heir traits are omitted from serialization, so a stored heir keeps following its grantor.
"""

from __future__ import annotations

import pytest
from core_10x.exec_control import CACHE_ONLY, GRAPH_OFF, GRAPH_ON
from core_10x.traitable import Traitable, XNone
from core_10x.traitable_heir import RT, T, TraitableHeir


class Conventions(TraitableHeir):
    mkt_name: str = T(T.ID)

    days_to_settle: int = T()  # -- heir trait
    calendar: str = RT()  # -- runtime heir trait
    currency: str = T('USD')  # -- has a default: not inherited
    lot_size: float = T()  # -- has a getter: not inherited

    def lot_size_get(self):
        return 1000.0


class XConventions(Conventions):
    tick_size: float = T()  # -- heir trait added by a subclass
    days_to_settle_twice: int = RT()

    def days_to_settle_twice_get(self):
        return 2 * self.days_to_settle


class Venue(Traitable):
    """A plain Traitable grantor of a different class; only `days_to_settle` matches by name."""

    name: str = T(T.ID)
    days_to_settle: int = T()


@pytest.fixture(params=[GRAPH_ON, GRAPH_OFF], ids=['graph_on', 'graph_off'])
def cache_only(request):
    with CACHE_ONLY(), request.param():
        yield


def make_grantor(mkt_name='WTI NYMEX', **values) -> Conventions:
    values = {'days_to_settle': 2, 'calendar': 'NYM', 'currency': 'EUR'} | values
    return Conventions(mkt_name=mkt_name, **values, _replace=True)


class TestHeirTraits:
    def test_only_traits_without_getter_or_default_are_heir_traits(self):
        assert {'days_to_settle', 'calendar'} <= set(Conventions.s_grantor_traits)
        assert not {'_grantor', 'currency', 'lot_size'} & set(Conventions.s_grantor_traits)

    def test_subclass_recomputes_heir_traits(self):
        assert {'days_to_settle', 'calendar', 'tick_size'} <= set(XConventions.s_grantor_traits)
        assert 'days_to_settle_twice' not in XConventions.s_grantor_traits
        assert 'tick_size' not in Conventions.s_grantor_traits


class TestInheritance:
    def test_unset_heir_traits_come_from_grantor(self, cache_only):
        grantor = make_grantor()
        heir = Conventions(mkt_name='WTI ICE', _grantor=grantor, _replace=True)

        assert heir.days_to_settle == 2
        assert heir.calendar == 'NYM'

    def test_traits_with_default_or_getter_are_not_inherited(self, cache_only):
        grantor = make_grantor()
        heir = Conventions(mkt_name='WTI ICE', _grantor=grantor, _replace=True)

        assert grantor.currency == 'EUR'
        assert heir.currency == 'USD'
        assert heir.lot_size == 1000.0

    def test_heir_follows_grantor_changes(self, cache_only):
        grantor = make_grantor()
        heir = Conventions(mkt_name='WTI ICE', _grantor=grantor, _replace=True)
        assert heir.days_to_settle == 2

        grantor.days_to_settle = 3
        assert heir.days_to_settle == 3

    def test_own_value_overrides_grantor_until_invalidated(self, cache_only):
        grantor = make_grantor()
        heir = Conventions(mkt_name='WTI ICE', _grantor=grantor, _replace=True)

        heir.days_to_settle = 5
        grantor.days_to_settle = 3
        assert heir.days_to_settle == 5
        assert grantor.days_to_settle == 3

        heir.invalidate_value('days_to_settle')
        assert heir.days_to_settle == 3

    def test_no_grantor_yields_xnone(self, cache_only):
        orphan = Conventions(mkt_name='orphan')
        assert orphan.days_to_settle is XNone

    def test_regranting(self, cache_only):
        nymex = make_grantor()
        ice = make_grantor('ICE', calendar='ICE')
        heir = Conventions(mkt_name='WTI ICE', _grantor=nymex, _replace=True)
        assert heir.calendar == 'NYM'

        heir._grantor = ice
        assert heir.calendar == 'ICE'

    def test_chain_of_grantors(self, cache_only):
        root = make_grantor()
        middle = Conventions(mkt_name='middle', _grantor=root, calendar='MID', _replace=True)
        leaf = Conventions(mkt_name='leaf', _grantor=middle, _replace=True)

        assert leaf.calendar == 'MID'
        assert leaf.days_to_settle == 2

        root.days_to_settle = 4
        assert leaf.days_to_settle == 4

    def test_grantor_of_another_class_matches_traits_by_name(self, cache_only):
        venue = Venue(name='CME', days_to_settle=7, _replace=True)
        heir = Conventions(mkt_name='WTI CME', _grantor=venue, _replace=True)

        assert heir.days_to_settle == 7
        assert heir.calendar is XNone  # -- Venue has no `calendar` trait

    def test_subclass_heir_from_base_class_grantor(self, cache_only):
        grantor = make_grantor()
        heir = XConventions(mkt_name='WTI ICE', _grantor=grantor, _replace=True)

        assert heir.days_to_settle_twice == 4
        assert heir.tick_size is XNone  # -- grantor's class has no `tick_size` trait


class TestSerialization:
    def test_unset_heir_traits_are_omitted(self, cache_only):
        grantor = make_grantor()
        heir = Conventions(mkt_name='WTI ICE', _grantor=grantor, _replace=True)

        data = heir.serialize_object()
        assert 'days_to_settle' not in data
        assert 'calendar' not in data  # -- runtime trait: never serialized
        assert data['currency'] == 'USD'
        assert data['_grantor']

    def test_own_values_are_serialized(self, cache_only):
        grantor = make_grantor()
        heir = Conventions(mkt_name='WTI ICE', _grantor=grantor, _replace=True)
        heir.days_to_settle = 5

        assert heir.serialize_object()['days_to_settle'] == 5

    def test_no_grantor(self, cache_only):
        data = Conventions(mkt_name='orphan').serialize_object()
        assert data['_grantor'] is None
        assert 'days_to_settle' not in data


@pytest.fixture
def store(ts_instance):
    ts_instance.username = 'test_user'
    ts_instance.begin_using()
    yield ts_instance
    for cn in ts_instance.collection_names():
        ts_instance.delete_collection(cn)
    ts_instance.end_using()


class TestStore:
    def test_stored_heir_keeps_following_grantor(self, store):
        grantor = Conventions(mkt_name='WTI NYMEX', days_to_settle=2, _replace=True)
        grantor.save().throw()
        heir = Conventions(mkt_name='WTI ICE', _grantor=grantor, _replace=True)
        heir.save().throw()

        record = next(doc for doc in Conventions.collection().find() if doc['_id'] == heir.id().value)
        assert 'days_to_settle' not in record

        grantor.days_to_settle = 3
        grantor.save().throw()

        loaded = Conventions.load(heir.id())
        assert loaded.days_to_settle == 3

    def test_stored_override_wins_over_grantor(self, store):
        grantor = Conventions(mkt_name='WTI NYMEX', days_to_settle=2, _replace=True)
        grantor.save().throw()
        heir = Conventions(mkt_name='WTI ICE', _grantor=grantor, _replace=True)
        heir.days_to_settle = 5
        heir.save().throw()

        loaded = Conventions.load(heir.id())
        assert loaded.days_to_settle == 5
