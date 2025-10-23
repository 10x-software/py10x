"""
Unit tests for converter methods in py10x traitables.
Tests verify that converter methods are called when appropriate.
"""

import pytest
from core_10x.exec_control import CONVERT_VALUES_OFF, CONVERT_VALUES_ON, DEBUG_OFF, DEBUG_ON, GRAPH_OFF, GRAPH_ON
from core_10x.traitable import Traitable


class Person(Traitable):
    """Test traitable with converter methods."""

    # Runtime traitable: omit T() so no storage context is required
    name: bytes
    status: str

    def name_from_str(self, trait, value: str) -> bytes:
        """Convert from string - title case the name."""
        return value.title().encode()

    def name_from_any_xstr(self, trait, value) -> bytes:
        """Convert from non-string - convert to string and title case."""
        return str(value).title().encode()

    def status_from_any_xstr(self, trait, value) -> bytes:
        """Convert any value to lowercase string."""
        return str(value).lower()


@pytest.mark.parametrize('graph_mode', [GRAPH_OFF, GRAPH_ON])
@pytest.mark.parametrize('debug_mode', [DEBUG_OFF, DEBUG_ON])
def test_converter_usage_with_execution_modes(graph_mode, debug_mode):
    """Test that converters work with different execution mode combinations."""
    with graph_mode(), debug_mode():
        with CONVERT_VALUES_ON():
            person = Person(name='john', status=True)
            assert person.name == b'John'
            assert person.status == 'true'
        with CONVERT_VALUES_OFF():
            person = Person()
            if debug_mode is DEBUG_ON:
                with pytest.raises(TypeError):
                    person.status = True
                with pytest.raises(TypeError):
                    person.name = 'john'
            else:
                person.name = 'john'
                person.status = True
                assert person.status is True
                assert person.name == 'john'
