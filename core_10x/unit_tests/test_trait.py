"""Tests for core_10x.trait.

Exercises the pure-Python surface of Trait:
- trait_value  — simple data container
- BoundTrait   — __call__ contract
- ClassTrait   — to_str, serialize/deserialize
- Trait.real_trait_class — registry dispatch
- Trait.use_format_str / _format — string formatting helpers
- Trait.register_by_datatype / register_by_baseclass — error on duplicate
"""
import sys
import types

import pytest
from unittest.mock import MagicMock

from core_10x.exec_control import CACHE_ONLY
from core_10x.trait import (
    BoundTrait,
    ClassTrait,
    Trait,
    generic_trait,
    trait_value,
)
from core_10x.trait_definition import T
from core_10x.traitable import Traitable


# ----------------------------------------------------------------------------
#   trait_value
# ----------------------------------------------------------------------------

def test_trait_value_stores_value_no_args():
    tv = trait_value(42)
    assert tv.value == 42
    assert tv.args == ()


def test_trait_value_stores_value_and_args():
    tv = trait_value('hello', 1, 2, 3)
    assert tv.value == 'hello'
    assert tv.args == (1, 2, 3)


def test_trait_value_is_callable_returns_none():
    tv = trait_value(99)
    result = tv()
    assert result is None


def test_trait_value_with_none_value():
    tv = trait_value(None)
    assert tv.value is None


# ----------------------------------------------------------------------------
#   BoundTrait
# ----------------------------------------------------------------------------

def test_bound_trait_call_returns_trait():
    mock_trait = MagicMock()
    bt = BoundTrait(None, mock_trait)
    assert bt() is mock_trait


def test_bound_trait_getattr_returns_trait_attribute():
    class _FakeTrait:
        name = 'my_trait'

    bt = BoundTrait(None, _FakeTrait())
    assert bt.name == 'my_trait'


# ----------------------------------------------------------------------------
#   Trait.real_trait_class — registry dispatch
# ----------------------------------------------------------------------------

def test_real_trait_class_for_completely_unregistered_type():
    class _PurelyCustomType:
        pass

    cls = Trait.real_trait_class(_PurelyCustomType)
    assert cls is generic_trait


def test_real_trait_class_for_int_is_not_generic():
    cls = Trait.real_trait_class(int)
    assert cls is not generic_trait


def test_real_trait_class_for_str_is_not_generic():
    cls = Trait.real_trait_class(str)
    assert cls is not generic_trait


# ----------------------------------------------------------------------------
#   Trait.register_by_datatype — duplicate raises
# ----------------------------------------------------------------------------

def test_register_by_datatype_duplicate_raises():
    # int is already registered; trying to re-register must fail.
    existing_cls = Trait.real_trait_class(int)
    with pytest.raises(AssertionError):
        Trait.register_by_datatype(existing_cls, int)


# ----------------------------------------------------------------------------
#   Trait.register_by_baseclass — duplicate raises
# ----------------------------------------------------------------------------

def test_register_by_baseclass_non_trait_raises():
    with pytest.raises(AssertionError):
        Trait.register_by_baseclass(int, int)


# ----------------------------------------------------------------------------
#   Trait._format / use_format_str
# ----------------------------------------------------------------------------

def _make_int_trait() -> Trait:
    int_trait_cls = Trait.real_trait_class(int)
    return int_trait_cls(T(data_type=int))


def test_format_empty_string_becomes_colon():
    t = _make_int_trait()
    assert t._format('') == '{:}'


def test_format_without_prefix_prepends_colon():
    t = _make_int_trait()
    assert t._format('.2f') == '{:.2f}'


def test_format_with_bang_prefix_unchanged():
    t = _make_int_trait()
    assert t._format('!r') == '{!r}'


def test_format_with_colon_prefix_unchanged():
    t = _make_int_trait()
    assert t._format(':>10') == '{:>10}'


def test_use_format_str_plain_string_no_fmt():
    t = _make_int_trait()
    assert t.use_format_str('', 'hello') == 'hello'


def test_use_format_str_int_no_fmt():
    t = _make_int_trait()
    assert t.use_format_str('', 42) == '42'


def test_use_format_str_with_fmt():
    t = _make_int_trait()
    assert t.use_format_str('04d', 7) == '0007'


def test_pybind_signature_parses_docstring_first_line():
    mod = types.ModuleType('fake_pybind_mod')
    sys.modules['fake_pybind_mod'] = mod

    def fake_get(self, x: int, y: float = 1.0) -> str:
        """fake_get(self, x: int, y: float = 1.0) -> str\n\nC++ getter."""
        raise AssertionError('must not call')

    fake_get.__module__ = 'fake_pybind_mod'
    sig = Trait.pybind_signature(fake_get)
    assert list(sig.parameters) == ['self', 'x', 'y']
    assert sig.parameters['y'].default == 1.0


# ----------------------------------------------------------------------------
#   ClassTrait
# ----------------------------------------------------------------------------

class _TestTraitable(Traitable):
    xid: int = T(T.ID, default=1)
    name: str = T()


def test_class_trait_to_str_includes_class_and_trait_name():
    with CACHE_ONLY():
        trait = _TestTraitable.trait('name')
        ct = ClassTrait(_TestTraitable, trait)
        s = ct.to_str()
        assert 'TestTraitable' in s or '_TestTraitable' in s
        assert 'name' in s


def test_class_trait_serialize_roundtrip():
    with CACHE_ONLY():
        trait = _TestTraitable.trait('name')
        ct = ClassTrait(_TestTraitable, trait)
        serialized = ct.serialize(embed=False)
        assert isinstance(serialized, list)
        assert len(serialized) == 2

        restored = ClassTrait.deserialize(serialized)
        assert restored.trait.name == 'name'
        assert restored.cls is _TestTraitable
