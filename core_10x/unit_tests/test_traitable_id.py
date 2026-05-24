import pytest

from core_10x.traitable_id import ID


# ----------------------------------------------------------------------------
#   Construction & basic attributes
# ----------------------------------------------------------------------------

def test_id_default_construction():
    i = ID()
    assert i.value is None
    assert i.collection_name is None


def test_id_with_value_only():
    i = ID('abc')
    assert i.value == 'abc'
    assert i.collection_name is None


def test_id_with_value_and_collection():
    i = ID('abc', 'col')
    assert i.value == 'abc'
    assert i.collection_name == 'col'


# ----------------------------------------------------------------------------
#   __bool__
# ----------------------------------------------------------------------------

def test_id_bool_truthy_with_value():
    assert ID('abc')
    assert bool(ID('abc', 'col'))


def test_id_bool_falsy_without_value():
    assert not ID()
    assert not ID(None)
    assert not ID('')


# ----------------------------------------------------------------------------
#   __repr__
# ----------------------------------------------------------------------------

def test_id_repr_without_collection():
    assert repr(ID('abc')) == 'abc'


def test_id_repr_with_collection():
    assert repr(ID('abc', 'col')) == 'col/abc'


def test_id_repr_none_value():
    assert repr(ID()) == 'None'


# ----------------------------------------------------------------------------
#   __eq__ and __hash__
# ----------------------------------------------------------------------------

def test_id_equality_same_value_and_collection():
    assert ID('x', 'c') == ID('x', 'c')


def test_id_equality_same_value_no_collection():
    assert ID('x') == ID('x')


def test_id_inequality_different_values():
    assert ID('x') != ID('y')


def test_id_inequality_different_collections():
    assert ID('x', 'a') != ID('x', 'b')


def test_id_not_equal_to_non_id():
    assert ID('x') != 'x'
    assert ID('x') != 42


def test_id_hashable_in_set():
    s = {ID('a', 'c'), ID('b', 'c'), ID('a', 'c')}
    assert len(s) == 2


def test_id_usable_as_dict_key():
    d = {ID('k', 'c'): 'value'}
    assert d[ID('k', 'c')] == 'value'


# ----------------------------------------------------------------------------
#   __lt__ and ordering (total_ordering)
# ----------------------------------------------------------------------------

def test_id_lt_compares_collection_first():
    # ('a', 'z') < ('b', 'a') because 'a' < 'b'
    assert ID('z', 'a') < ID('a', 'b')


def test_id_lt_compares_value_when_collection_equal():
    assert ID('a', 'c') < ID('b', 'c')


def test_id_not_lt_when_equal():
    assert not (ID('a', 'c') < ID('a', 'c'))


def test_id_total_ordering_le_ge_gt():
    assert ID('a') <= ID('a')
    assert ID('a') <= ID('b')
    assert ID('b') >= ID('a')
    assert ID('b') > ID('a')


def test_id_sortable():
    ids = [ID('c'), ID('a'), ID('b')]
    assert sorted(ids) == [ID('a'), ID('b'), ID('c')]


def test_id_lt_none_collection_raises_type_error_vs_named():
    # Python 3 does not order None against strings, so mixing None and non-None
    # collection_names raises TypeError — document that boundary here.
    with pytest.raises(TypeError):
        _ = ID('z', None) < ID('a', 'c')


def test_id_lt_returns_not_implemented_for_non_id():
    result = ID('a').__lt__('x')
    assert result is NotImplemented


def test_id_eq_returns_not_implemented_for_non_id():
    result = ID('a').__eq__('x')
    assert result is NotImplemented
