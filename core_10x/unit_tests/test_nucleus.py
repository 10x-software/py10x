from __future__ import annotations

import pytest

from core_10x.nucleus import Nucleus


# ----------------------------------------------------------------------------
#   Minimal concrete subclass used by the tests below
# ----------------------------------------------------------------------------

class _SimpleNucleus(Nucleus):
    def __init__(self, v):
        self._v = v

    def to_str(self) -> str:
        return str(self._v)

    def serialize(self, embed: bool):
        return self._v

    @classmethod
    def deserialize(cls, serialized_data) -> _SimpleNucleus:
        return cls(serialized_data)

    @classmethod
    def from_str(cls, s: str) -> _SimpleNucleus:
        return cls(s)

    @classmethod
    def from_any_xstr(cls, value) -> _SimpleNucleus:
        return cls(value)

    @classmethod
    def same_values(cls, value1, value2) -> bool:
        return isinstance(value2, cls) and value1._v == value2._v


# ----------------------------------------------------------------------------
#   Class-level tag constants
# ----------------------------------------------------------------------------

def test_nucleus_tags_are_exposed():
    for tag in ('TYPE_TAG', 'CLASS_TAG', 'REVISION_TAG', 'OBJECT_TAG',
                'COLLECTION_TAG', 'ID_TAG', 'NX_RECORD_TAG',
                'TYPE_RECORD_TAG', 'PICKLE_RECORD_TAG'):
        assert hasattr(Nucleus, tag), f'Nucleus is missing {tag}'


def test_nucleus_serialization_methods_exposed():
    for name in ('serialize_any', 'deserialize_any', 'serialize_type',
                 'deserialize_type', 'serialize_complex', 'deserialize_complex',
                 'serialize_date', 'deserialize_date', 'serialize_list',
                 'deserialize_list', 'serialize_dict', 'deserialize_dict',
                 'deserialize_record'):
        assert callable(getattr(Nucleus, name)), f'Nucleus.{name} is not callable'


# ----------------------------------------------------------------------------
#   choose_from
# ----------------------------------------------------------------------------

def test_nucleus_choose_from_returns_empty_dict():
    assert Nucleus.choose_from() == {}
    assert _SimpleNucleus.choose_from() == {}


# ----------------------------------------------------------------------------
#   from_any dispatch
# ----------------------------------------------------------------------------

def test_from_any_returns_self_when_already_correct_instance():
    n = _SimpleNucleus('hello')
    assert _SimpleNucleus.from_any(n) is n


def test_from_any_calls_from_str_for_strings():
    result = _SimpleNucleus.from_any('world')
    assert isinstance(result, _SimpleNucleus)
    assert result._v == 'world'


def test_from_any_calls_from_any_xstr_for_other_types():
    result = _SimpleNucleus.from_any(42)
    assert isinstance(result, _SimpleNucleus)
    assert result._v == 42


def test_from_any_with_list_value():
    result = _SimpleNucleus.from_any([1, 2, 3])
    assert isinstance(result, _SimpleNucleus)
    assert result._v == [1, 2, 3]


# ----------------------------------------------------------------------------
#   __repr__ and __eq__
# ----------------------------------------------------------------------------

def test_nucleus_repr_delegates_to_to_str():
    n = _SimpleNucleus('my-value')
    assert repr(n) == 'my-value'


def test_nucleus_eq_equal_values():
    assert _SimpleNucleus('x') == _SimpleNucleus('x')


def test_nucleus_eq_unequal_values():
    assert _SimpleNucleus('x') != _SimpleNucleus('y')


def test_nucleus_eq_different_type():
    n = _SimpleNucleus('x')
    assert n != 'x'


# ----------------------------------------------------------------------------
#   to_id defaults to to_str
# ----------------------------------------------------------------------------

def test_to_id_defaults_to_to_str():
    n = _SimpleNucleus('my-id')
    assert n.to_id() == 'my-id'


# ----------------------------------------------------------------------------
#   Abstract methods raise NotImplementedError on the base class
# ----------------------------------------------------------------------------

def test_base_serialize_raises_not_implemented():
    n = object.__new__(Nucleus)
    with pytest.raises(NotImplementedError):
        n.serialize(embed=True)


def test_base_deserialize_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        Nucleus.deserialize(None)


def test_base_from_str_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        Nucleus.from_str('x')


def test_base_from_any_xstr_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        Nucleus.from_any_xstr(1)


def test_base_same_values_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        Nucleus.same_values(None, None)


# ----------------------------------------------------------------------------
#   Concrete subclass round-trip
# ----------------------------------------------------------------------------

def test_concrete_serialize_deserialize_round_trip():
    original = _SimpleNucleus('round-trip')
    serialized = original.serialize(embed=False)
    restored = _SimpleNucleus.deserialize(serialized)
    assert original == restored
