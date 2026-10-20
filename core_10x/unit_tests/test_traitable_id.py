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


# ---------------------------------------------------------------------------
# Unshared IDs, and agreement with the kernel's TID
# ---------------------------------------------------------------------------


def test_unshared_ids_are_distinct():
    """Two objects under construction are not the same entity, so their (valueless) IDs
    must not compare equal -- otherwise a set collapses them and only one survives."""
    a, b = ID(), ID()
    alias = a
    assert a == alias, 'an unshared ID is still equal to itself'
    assert a != b


def test_unshared_id_is_not_equal_to_a_valued_one():
    assert ID() != ID('x')
    assert ID('x') != ID()


def test_id_eq_and_hash_agree_with_tid():
    """Python's ID rule (traitable_id.py) and the kernel's TID rule (cxx10x tid.h) are two
    separate implementations of one contract; this holds them together."""
    from core_10x.exec_control import CACHE_ONLY, INTERACTIVE
    from core_10x.trait_definition import T
    from core_10x.traitable import Traitable

    class Q(Traitable):
        name: str = T(T.ID)

    with CACHE_ONLY(), INTERACTIVE():
        unshared_a, unshared_b = Q(), Q()
        shared = Q(name='q', _replace=True)
        same_id = Q(name='q')

        for left, right in ((unshared_a, unshared_a), (unshared_a, unshared_b), (shared, same_id), (unshared_a, shared)):
            assert (left.id() == right.id()) is left.xid()._equals(right.xid()), (left.id(), right.id())
            if left.id() == right.id() and left.id().value is not None:
                assert hash(left.id()) == hash(right.id())
            # The kernel still hashes invalid TIDs -- it needs them distinct inside
            # tracked_objects(), whose set never outlives the call.
            assert left.xid()._hash() == right.xid()._hash() or left.id() != right.id()


def test_unshared_traitable_cannot_be_put_in_a_set():
    """Refused rather than silently filed under a hash share() will change.

    Hashing an unshared traitable and then sharing it would leave the entry under the old
    hash: `in`, .get() and .remove() would all miss it while it kept the object alive. The
    kernel still hashes an invalid TID internally -- see _hash above -- because the
    containers it uses for those never outlive the share.
    """
    from core_10x.exec_control import CACHE_ONLY, INTERACTIVE
    from core_10x.trait_definition import T
    from core_10x.traitable import Traitable

    class R(Traitable):
        name: str = T(T.ID)

    with CACHE_ONLY(), INTERACTIVE():
        pending = R()
        with pytest.raises(TypeError, match='not hashable'):
            set().add(pending)
        with pytest.raises(TypeError, match='not hashable'):
            hash(pending.id())

        pending.name = 'landed'
        assert pending.share(False)

        # Hashable once the ID has landed, and stable from here on.
        holder = {pending}
        assert pending in holder
        assert hash(pending) == hash(R(name='landed'))
