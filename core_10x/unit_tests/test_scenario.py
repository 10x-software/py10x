"""Unit tests for core_10x/scenario.py."""
import pytest

from core_10x.scenario import Scenario


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
        with pytest.raises(ValueError, match='test error'):
            with Scenario('scen_test_ctx_D'):
                raise ValueError('test error')
