"""Unit tests for core_10x/scenario.py."""

from __future__ import annotations

import functools
from weakref import WeakKeyDictionary

import pytest
from core_10x.exec_control import CACHE_ONLY
from core_10x.scenario import Scenario
from core_10x.traitable import RT, T, Traitable
from core_10x.xnone import XNone


class TestScenarioIdentity:
    def test_named_scenario_is_singleton(self):
        """The same name always returns the same instance."""
        s1 = Scenario('scen_test_A')
        s2 = Scenario('scen_test_A')
        assert s1 is s2

    def test_different_names_are_different_instances(self):
        s1 = Scenario('scen_test_B')
        s2 = Scenario('scen_test_C')
        assert s1 is not s2

    def test_anonymous_is_not_singleton(self):
        """Scenario() with no name creates a fresh instance each call."""
        s1 = Scenario()
        s2 = Scenario()
        assert s1 is not s2

    def test_named_has_correct_name(self):
        s = Scenario('scen_test_D')
        assert s.name == 'scen_test_D'

    def test_anonymous_has_none_name(self):
        s = Scenario()
        assert s.name is None

    def test_named_scenario_has_btp(self):
        s = Scenario('scen_test_E')
        assert s.btp is not None

    def test_anonymous_scenario_has_btp_before_use(self):
        s = Scenario()
        assert s.btp is not None


class TestScenarioContextManager:
    def test_context_manager_returns_self(self):
        s = Scenario('scen_test_ctx_A')
        with s as ctx:
            assert ctx is s

    def test_named_scenario_btp_persists_after_exit(self):
        """Named scenarios keep their BTP so they can be re-entered."""
        s = Scenario('scen_test_ctx_B')
        with s:
            pass
        assert s.btp is not None

    def test_anonymous_scenario_btp_cleared_after_exit(self):
        """Anonymous scenarios discard their BTP on exit."""
        s = Scenario()
        with s:
            pass
        assert s.btp is None

    def test_named_scenario_can_be_entered_multiple_times(self):
        """Re-entering a named scenario must not raise."""
        s = Scenario('scen_test_ctx_C')
        with s:
            pass
        with s:
            pass

    def test_exception_propagates_through_context_manager(self):
        """Exceptions inside the with-block are not swallowed."""
        with pytest.raises(ValueError, match='test error'), Scenario('scen_test_ctx_D'):
            raise ValueError('test error')


# ---------------------------------------------------------------------------
# Helpers shared by E2E tests
# ---------------------------------------------------------------------------


def call_counter(method):
    """Decorator that counts per-instance getter invocations."""

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        wrapper.call_counts[self] = wrapper.call_counts.get(self, 0) + 1
        return method(self, *args, **kwargs)

    wrapper.call_counts = WeakKeyDictionary()
    wrapper.count = lambda obj: wrapper.call_counts.get(obj, 0)
    return wrapper


# ---------------------------------------------------------------------------
# End-to-end: Traitable computations inside Scenario contexts
# ---------------------------------------------------------------------------


class TestScenarioEndToEnd:
    """
    Verifies that a Scenario actually activates GRAPH_ON semantics:
    computed traits are cached, dependency invalidation works, and
    named-scenario re-entry gives access to the same BTP/cache scope.
    """

    class Price(Traitable):
        ticker: str = T(T.ID)
        raw: float = T()
        adjusted: float = RT()

        @call_counter
        def adjusted_get(self) -> float:
            return self.raw * 1.1

    def test_computed_trait_is_cached_inside_scenario(self):
        """Inside Scenario (GRAPH_ON), the getter runs once; repeated reads hit the cache."""
        with CACHE_ONLY(), Scenario('e2e_cache_A'):
            p = self.Price(ticker='e2e_AAPL_A')
            p.raw = 100.0
            v1 = p.adjusted  # getter invoked → count = 1
            v2 = p.adjusted  # cache hit → count stays 1
            assert self.Price.adjusted_get.count(p) == 1
            assert v1 == v2 == pytest.approx(110.0)

    def test_dependency_invalidation_triggers_recompute(self):
        """Changing a dependency invalidates the cached value; next read recomputes."""
        with CACHE_ONLY(), Scenario('e2e_dep_B'):
            p = self.Price(ticker='e2e_AAPL_B')
            p.raw = 100.0
            _ = p.adjusted  # compute and cache
            p.raw = 200.0  # invalidate dependency
            v = p.adjusted  # must recompute
            assert v == pytest.approx(220.0)
            assert self.Price.adjusted_get.count(p) == 2

    def test_named_scenario_reentry_sees_same_cached_data(self):
        """Data written during the first entry is visible when the Scenario is re-entered."""
        with CACHE_ONLY():
            with Scenario('e2e_reentry_C'):
                p = self.Price(ticker='e2e_AAPL_C')
                p.raw = 50.0
                _ = p.adjusted  # cache value = 55.0

            with Scenario('e2e_reentry_C'):  # same BTP, same cache
                p2 = self.Price(ticker='e2e_AAPL_C')
                assert p2.raw == 50.0
                assert p2.adjusted == pytest.approx(55.0)
                # Getter must NOT have been called again (value still cached)
                assert self.Price.adjusted_get.count(p) == 1

    def test_different_named_scenarios_have_independent_btps(self):
        """Two distinct names produce distinct BTP objects."""
        s1 = Scenario('e2e_ind_D1')
        s2 = Scenario('e2e_ind_D2')
        assert s1.btp is not s2.btp

    def test_scenario_is_reusable_in_loop(self):
        """A named Scenario can be entered and exited many times without error."""
        s = Scenario('e2e_reuse_E')
        for _ in range(5):
            with s:
                pass

    def test_nested_scenario_inherits_parent_values(self):
        """A nested Scenario starts with the parent scope's data visible.

        Values written in the outer Scenario must be readable in the inner one
        before the inner Scenario overrides them. After the inner Scenario exits,
        the outer scope is restored unchanged.
        """
        with CACHE_ONLY(), Scenario('e2e_outer_G'):
            p = self.Price(ticker='e2e_MSFT_G')
            p.raw = 100.0
            outer_adj = p.adjusted  # caches 110.0 in outer BTP

            with Scenario('e2e_inner_G'):
                # Parent-scope value is visible before any override
                assert p.raw == 100.0

                # Override inside the inner scope
                p.raw = 200.0
                inner_adj = p.adjusted  # recomputes to 220.0
                assert inner_adj == pytest.approx(220.0)

            # After inner exits, outer scope is restored
            assert p.raw == 100.0
            assert p.adjusted == pytest.approx(outer_adj)


# ---------------------------------------------------------------------------
# A Scenario owns the containers it takes from the outer scope
# ---------------------------------------------------------------------------


class TestScenarioOwnsItsContainers:
    """
    A list, set or dict set in the outer scope is copied when an inner Scenario first reads it,
    so changing it in place inside the Scenario cannot reach the outer scope.
    """

    class Bag(Traitable):
        name: str = T(T.ID)
        items: list = RT([])
        tags: set = RT()
        attrs: dict = RT()
        label: tuple = RT()
        total: int = RT()

        def total_get(self) -> int:
            return sum(self.items)

    def test_in_place_change_stays_inside(self):
        with CACHE_ONLY(), Scenario('own_outer_A'):
            b = self.Bag(name = 'own_A')
            b.items, b.tags, b.attrs = [1, 2], {'a'}, {'k': 1}
            assert b.total == 3

            with Scenario():
                b.items.append(3)
                b.tags.add('b')
                b.attrs['k'] = 2
                assert (b.items, b.tags, b.attrs) == ([1, 2, 3], {'a', 'b'}, {'k': 2})

            assert (b.items, b.tags, b.attrs) == ([1, 2], {'a'}, {'k': 1})
            assert b.total == 3

    def test_set_back_inside_does_not_reach_outside(self):
        """Changed in place and set back on the trait: the Scenario sees it, the outer scope does not."""
        with CACHE_ONLY(), Scenario('own_outer_B'):
            b = self.Bag(name = 'own_B')
            b.items = [1, 2]
            assert b.total == 3

            with Scenario():
                v = b.items
                v.append(3)
                b.items = v
                assert b.total == 6

            assert b.items == [1, 2]
            assert b.total == 3

    def test_one_copy_per_scope(self):
        with CACHE_ONLY(), Scenario('own_outer_C'):
            b = self.Bag(name = 'own_C')
            b.items = [1, 2]
            outer = b.items

            with Scenario():
                inner = b.items
                assert inner == outer
                assert inner is not outer
                assert b.items is inner

            assert b.items is outer

    def test_other_values_pass_as_they_are(self):
        """XNone, a value of another type, and a value that cannot change in place are not copied."""
        with CACHE_ONLY(), Scenario('own_outer_D'):
            b = self.Bag(name = 'own_D')
            mistyped = (1, 2)
            b.items = mistyped
            b.tags = XNone
            b.label = ('x', 'y')
            outer_label = b.label

            with Scenario():
                assert b.items is mistyped
                assert b.tags is XNone
                assert b.label is outer_label

    def test_shallow_copy_of_the_trait_classes(self):
        bag = self.Bag
        for name, value in (('items', [1, [2]]), ('tags', {1, 2}), ('attrs', {'k': [1]})):
            copied = bag.trait(name).shallow_copy(value)
            assert copied == value
            assert copied is not value
        inner = [2]
        assert bag.trait('items').shallow_copy([1, inner])[1] is inner  # one level only
        label = ('x',)
        assert bag.trait('label').shallow_copy(label) is label
