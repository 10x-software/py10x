from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pytest
import uuid6
from core_10x.exec_control import CACHE_ONLY, GRAPH_OFF
from core_10x.named_constant import EnumBits, NamedConstant
from core_10x.nucleus import Nucleus
from core_10x.testlib import test_databases
from core_10x.testlib.strict import need
from core_10x.trait_definition import T
from core_10x.trait_filter import (
    AND,
    BETWEEN,
    EQ,
    FALSE,
    GE,
    GT,
    IN,
    LE,
    LT,
    NE,
    NIN,
    NOT,
    NOT_EMPTY,
    OR,
    BoolOp,
    f,
)
from core_10x.traitable import Traitable, XNone
from core_10x.ts_store import TsStore
from core_10x.ts_store_type import TS_STORE_TYPE
from py10x_kernel import BTraitableProcessor


class Person(Traitable):
    first_name: str
    last_name: str
    age: int
    dob: date


def test_filters():
    p = Person(first_name='Sasha', last_name='Davidovich')

    r = OR(f(age=BETWEEN(50, 70), first_name=NE('Sasha')), f(age=17))

    assert r.prefix_notation() == {'$or': [{'$and': [{'age': {'$gte': 50, '$lte': 70}}, {'first_name': {'$ne': 'Sasha'}}]}, {'age': {'$eq': 17}}]}
    assert not r.eval(p)


def test_or():
    p = Person(first_name='Sasha', last_name='Davidovich')
    r1, r2 = f(age=BETWEEN(50, 70)), f(first_name=EQ('Sasha'))
    r3 = OR(r1, r2)
    r4 = OR(r1)
    r5 = OR(r2)
    r6 = OR()
    assert r1.prefix_notation() == {'age': {'$gte': 50, '$lte': 70}}
    assert r2.prefix_notation() == {'first_name': {'$eq': 'Sasha'}}
    assert r3.prefix_notation() == {'$or': [r1.prefix_notation(), r2.prefix_notation()]}

    assert r4.prefix_notation() == r1.prefix_notation()
    assert r5.prefix_notation() == r2.prefix_notation()
    assert r6.prefix_notation() == {'$expr': False}

    assert not r1.eval(p)
    assert r2.eval(p)
    assert r3.eval(p)
    assert not r4.eval(p)
    assert r5.eval(p)
    assert not r6.eval(p)

    r7 = OR(OR(), OR())
    assert r7.prefix_notation() == {'$expr': False}
    assert not r7.eval(p)

    r8 = OR(OR(), AND())
    assert r7.prefix_notation() == {'$expr': False}
    assert r8.eval(p)


def test_and():
    p = Person(first_name='Sasha', last_name='Davidovich')

    r1, r2 = f(age=BETWEEN(50, 70)), f(first_name=EQ('Sasha'))
    r3 = AND(r1, r2)
    r4 = AND(r1)
    r5 = AND(r2)
    r6 = AND()
    assert r1.prefix_notation() == {'age': {'$gte': 50, '$lte': 70}}
    assert r2.prefix_notation() == {'first_name': {'$eq': 'Sasha'}}
    assert r3.prefix_notation() == {'$and': [r1.prefix_notation(), r2.prefix_notation()]}

    assert r4.prefix_notation() == r1.prefix_notation()
    assert r5.prefix_notation() == r2.prefix_notation()
    assert r6.prefix_notation() == {}

    assert not r1.eval(p)
    assert r2.eval(p)
    assert not r3.eval(p)
    assert not r4.eval(p)
    assert r5.eval(p)
    assert r6.eval(p)

    r7 = AND(AND(), AND())
    assert r7.prefix_notation() == {}
    assert r7.eval(p)

    r8 = AND(AND(), OR())
    assert r8.prefix_notation() == {'$expr': False}
    assert not r8.eval(p)


def test_simple_ops_eval_and_prefix():
    assert EQ(5).eval(5)
    assert not EQ(5).eval(4)
    assert EQ('x').prefix_notation() == {'$eq': 'x'}

    assert NE(5).eval(4)
    assert not NE(5).eval(5)
    assert NE('x').prefix_notation() == {'$ne': 'x'}

    assert GT(5).eval(6)
    assert not GT(5).eval(5)
    assert GT(5).prefix_notation() == {'$gt': 5}

    assert GE(5).eval(5)
    assert GE(5).eval(6)
    assert not GE(5).eval(4)
    assert GE(5).prefix_notation() == {'$gte': 5}

    assert LT(5).eval(4)
    assert not LT(5).eval(5)
    assert LT(5).prefix_notation() == {'$lt': 5}

    assert LE(5).eval(5)
    assert LE(5).eval(4)
    assert not LE(5).eval(6)
    assert LE(5).prefix_notation() == {'$lte': 5}


def test_in_nin():
    assert IN([1, 2, 3]).eval(2)
    assert not IN([1, 2, 3]).eval(4)
    assert IN((1, 2)).prefix_notation() == {'$in': (1, 2)}

    assert NIN([1, 2, 3]).eval(4)
    assert not NIN([1, 2, 3]).eval(2)
    assert NIN([1, 2]).prefix_notation() == {'$nin': [1, 2]}

    # set is also accepted
    assert IN({1, 2, 3}).eval(2)
    assert not IN({1, 2, 3}).eval(4)
    assert IN({1, 2, 3}).prefix_notation() == {'$in': {1, 2, 3}}

    assert NIN({1, 2, 3}).eval(4)
    assert not NIN({1, 2, 3}).eval(2)

    with pytest.raises(AssertionError, match='requires a list, tuple, or set'):
        IN(42)


def test_any_trait_has_no_item_match_eval():
    class AnyEval(Traitable):
        marker: str = T(T.ID)
        v: Any = T()
        lst: list = T()
        st: set = T()

    with CACHE_ONLY():
        x = AnyEval(marker='x')
        x.v, x.lst, x.st = [10, 20], [10, 20], {10, 20}
        assert not f(v=10).eval(x)
        assert f(v=NE(10)).eval(x)
        assert not f(v=IN([10])).eval(x)
        assert f(v=NIN([10])).eval(x)
        assert f(v=NOT(EQ(10))).eval(x)
        assert f(v=[10, 20]).eval(x)
        assert f(v=IN([[10, 20]])).eval(x)
        assert f(lst=10).eval(x)
        assert f(st=10).eval(x)
        for field in ('v', 'lst', 'st'):
            assert not f(**{field: GT(5)}).eval(x)
            assert not f(**{field: LT(50)}).eval(x)
            assert not f(**{field: BETWEEN(12, 14)}).eval(x)
            assert f(**{field: NOT(GT(5))}).eval(x)


class NoneSaved(Traitable, keep_history=False):
    marker: str = T(T.ID)
    n: int = T()
    lst: list = T()


def test_none_filter_value_is_up_to_the_serializer():
    class NoneValue(Traitable):
        marker: str = T(T.ID)
        age: int = T()
        name: str = T()
        v: Any = T()
        when: date = T()
        dct: dict = T()

    td = NoneValue.s_dir
    assert f(age=None, trait_dir=td).prefix_notation() == {'age': {'$eq': None}}
    assert f(name=NE(None), trait_dir=td).prefix_notation() == {'name': {'$ne': None}}
    assert f(age=IN([None, 1]), trait_dir=td).prefix_notation() == {'age': {'$in': [None, 1]}}
    assert f(v=None, trait_dir=td).prefix_notation() == {'v': {'$in': [None], '$not': {'$type': 'array'}}}
    for name in ('when', 'dct'):
        with pytest.raises(AttributeError):
            f(**{name: None}, trait_dir=td).prefix_notation()


def test_prefix_notation_guards_only_list_set_and_any_traits():
    class Guarded(Traitable):
        marker: str = T(T.ID)
        age: int = T()
        dct: dict = T()
        v: Any = T()
        lst: list = T()
        st: set = T()

    td = Guarded.s_dir
    not_array = {'$not': {'$type': 'array'}}
    # -- other traits, and fields with no trait, stay plain
    assert f(age=10, trait_dir=td).prefix_notation() == {'age': {'$eq': 10}}
    assert f(age=GT(5), trait_dir=td).prefix_notation() == {'age': {'$gt': 5}}
    assert f(age=BETWEEN(1, 5), trait_dir=td).prefix_notation() == {'age': {'$gte': 1, '$lte': 5}}
    assert f(dct={'a': 1}, trait_dir=td).prefix_notation() == {'dct': EQ({'a': 1}).prefix_notation('dct', td)}
    assert f(_id='x', trait_dir=td).prefix_notation() == {'_id': {'$eq': 'x'}}
    assert f(v=10).prefix_notation() == {'v': {'$eq': 10}}
    assert f(v=GT(5)).prefix_notation() == {'v': {'$gt': 5}}
    # -- a list trait matches items, unless a str or None could hit the stored class id
    assert f(lst=10, trait_dir=td).prefix_notation() == {'lst': {'$eq': 10}}
    assert f(st=10, trait_dir=td).prefix_notation() == {'st': {'$eq': 10}}
    # -- any-typed: the whole value
    assert f(v=10, trait_dir=td).prefix_notation() == {'v': {'$in': [10], **not_array}}
    # -- ordered operators never look inside an array
    for name in ('v', 'lst', 'st'):
        assert f(**{name: GT(5)}, trait_dir=td).prefix_notation() == {name: {'$gt': 5, **not_array}}
    assert f(v=BETWEEN(1, 5), trait_dir=td).prefix_notation() == {'v': {'$gte': 1, '$lte': 5, **not_array}}
    assert f(v=NOT(GT(5)), trait_dir=td).prefix_notation() == {'$nor': [{'v': {'$gt': 5, **not_array}}]}


def test_list_trait_item_match_eval_and_prefix():
    # a scalar against a list trait matches an item; a collection matches the whole list
    td = Sample.s_dir
    assert f(lst=10, trait_dir=td).prefix_notation() == {'lst': {'$eq': 10}}
    assert f(lst=NE(10), trait_dir=td).prefix_notation() == {'lst': {'$ne': 10}}
    assert f(lst=IN([10, 99]), trait_dir=td).prefix_notation() == {'lst': {'$in': [10, 99]}}
    assert f(lst=NIN([10]), trait_dir=td).prefix_notation() == {'lst': {'$nin': [10]}}
    assert f(lst=[10, 20], trait_dir=td).prefix_notation() == {'lst': {'$eq': ['builtins/int', 10, 20]}}
    assert f(lst=(10, 20), trait_dir=td).prefix_notation() == {'lst': {'$eq': ['builtins/int', 10, 20]}}
    assert f(lst=XNone, trait_dir=td).prefix_notation()['lst'] == {'$in': [None]}

    for left in ([10, 20], {10, 20}):
        assert EQ(10).eval(left, 'lst', td)
        assert not EQ(99).eval(left, 'lst', td)
        assert NE(99).eval(left, 'lst', td)
        assert not NE(10).eval(left, 'lst', td)
        assert IN([99, 20]).eval(left, 'lst', td)
        assert not IN([99]).eval(left, 'lst', td)
        assert NIN([99]).eval(left, 'lst', td)
        assert not NIN([99, 10]).eval(left, 'lst', td)
        assert NOT(EQ(99)).eval(left, 'lst', td)
        assert not BETWEEN(5, 50).eval(left, 'lst', td)
        # -- no list trait: a scalar compares to the whole value, so it never equals a list
        assert not EQ(10).eval(left)
        assert NE(10).eval(left)
        assert not IN([10]).eval(left)
        assert NIN([10]).eval(left)

    # whole-list match, incl. a tuple (serialized as a list, as Mongo sees it)
    assert EQ([10, 20]).eval([10, 20])
    assert EQ((10, 20)).eval([10, 20])
    assert not EQ([10]).eval([10, 20])
    assert IN([(10, 20)]).eval([10, 20])
    assert NE((10,)).eval([10, 20])


def test_between_bounds_and_prefix():
    b = BETWEEN(1, 5)
    assert b.eval(3)
    assert b.eval(1)
    assert b.eval(5)
    assert not b.eval(0)
    assert not b.eval(6)
    assert b.prefix_notation() == {'$gte': 1, '$lte': 5}

    b_ex = BETWEEN(1, 5, bounds=(False, False))
    assert b_ex.eval(2)
    assert not b_ex.eval(1)
    assert not b_ex.eval(5)
    assert b_ex.prefix_notation() == {'$gt': 1, '$lt': 5}


def test_not_empty_and_bool_ops_eval_and_prefix():
    assert NOT_EMPTY().eval('abc')
    assert not NOT_EMPTY().eval('')
    with pytest.raises(NotImplementedError):
        NOT_EMPTY().prefix_notation()

    a = AND(EQ(5), GT(3))
    assert a.eval(5)
    assert not a.eval(3)
    assert a.prefix_notation() == {'$and': [{'$eq': 5}, {'$gt': 3}]}

    o = OR(EQ(1), EQ(2))
    assert o.eval(1)
    assert o.eval(2)
    assert not o.eval(3)
    assert o.prefix_notation() == {'$or': [{'$eq': 1}, {'$eq': 2}]}

    # single-argument behaviors: prefix_notation returns inner dict
    single_and = AND(EQ(7))
    assert single_and.prefix_notation() == {'$eq': 7} or single_and.prefix_notation() == {'$eq': 7}

    # empty BoolOp
    assert OR().prefix_notation() == {'$expr': False}
    assert AND().prefix_notation() == {}


def test_field_op_and_false_sentinel():
    assert f(age=IN([])).prefix_notation() == {'age': {'$in': []}}
    assert OR() is BoolOp.s_false
    assert IN([]) is not FALSE()

    # Mongo has no field-level $and/$or, and FALSE is a whole-query filter.
    for bad in (OR(EQ(1), EQ(2)), AND(GT(1), LT(5)), AND(), OR(), f(age=1), NOT(OR(EQ(1), EQ(2)))):
        with pytest.raises(AssertionError):
            f(age=bad)


def test_f_named_expressions_eval_and_prefix():
    d = Person(age=10, first_name='Bob', last_name='')

    # named expressions may be raw values (wrapped to EQ) or filters
    filt = f(age=EQ(10), first_name='Bob')
    assert filt.eval(d)
    assert filt.prefix_notation() == {'$and': [{'age': {'$eq': 10}}, {'first_name': {'$eq': 'Bob'}}]}

    # mismatch
    filt2 = f(age=EQ(11), first_name='Bob')
    assert not filt2.eval(d)

    # ensure f uses Person.get_value for named fields
    assert f(age=10).eval(d)  # 10 wrapped as EQ(10) -> matches d.get_value('age') == 10
    assert not f(age=9).eval(d)

    # f with multiple named expressions
    multi = f(age=EQ(10), first_name=NE('Alice'), last_name=NOT_EMPTY())
    assert multi.eval(Person(age=10, first_name='Bob', last_name='Smith'))
    assert not f(last_name=NOT_EMPTY()).eval(Person(last_name=''))  # empty string -> NOT_EMPTY false


def test_empty_f_is_no_constraint():
    with CACHE_ONLY():
        a = Person(first_name='A', last_name='A')
        b = Person(first_name='B', last_name='B')
        empty = f()
        assert empty.eval(a) is True
        assert empty.eval(b) is True
        assert empty.prefix_notation() == {}
        ids = {p.id() for p in Person.existing_instances_by_filter(empty)}
        assert a.id() in ids and b.id() in ids


def test_existing_instances_by_filter_prefers_in_memory_over_stale_store(ts_instance):
    """A store match must not override the current in-memory value: once an
    object is loaded, an unsaved edit that no longer matches the filter is
    excluded, and one that newly matches is found -- even though the store
    itself hasn't changed (nothing here is ever saved).
    """

    class Widget(Traitable, custom_collection=True):
        key: str = T(T.ID)
        tag: str = T(default='')

    coll_name = f'eibf_{uuid6.uuid7().hex[:12]}'
    with ts_instance:
        try:
            w = Widget(key='w1', tag='a', _collection_name=coll_name, _replace=True)
            w.save().throw()

            found = {p.id() for p in Widget.existing_instances_by_filter(f(tag='a'), _coll_name=coll_name)}
            assert w.id() in found

            # Stage an edit without saving -- the store still says tag='a'.
            w.tag = 'b'

            still_a = {p.id() for p in Widget.existing_instances_by_filter(f(tag='a'), _coll_name=coll_name)}
            assert w.id() not in still_a, 'a stale store match for an already-loaded, now-diverged object must not be returned'

            now_b = {p.id() for p in Widget.existing_instances_by_filter(f(tag='b'), _coll_name=coll_name)}
            assert w.id() in now_b, 'a staged-but-unsaved in-memory match must be found even though the store disagrees'
        finally:
            Widget.delete_collection(coll_name)


def test_existing_instances_by_filter_finds_store_only_match_not_yet_in_memory(ts_instance):
    """An entity that exists in the store but hasn't been touched in the
    current scope yet must still be found (the discovery path)."""

    class Widget2(Traitable, custom_collection=True):
        key: str = T(T.ID)
        tag: str = T(default='')

    coll_name = f'eibf2_{uuid6.uuid7().hex[:12]}'
    with ts_instance:
        try:
            with BTraitableProcessor.create_root():
                Widget2(key='w1', tag='a', _collection_name=coll_name, _replace=True).save().throw()

            found = {p.id().value for p in Widget2.existing_instances_by_filter(f(tag='a'), _coll_name=coll_name)}
            assert 'w1' in found
        finally:
            Widget2.delete_collection(coll_name)


def test_empty_in_nin_eval():
    assert not IN([]).eval(1)
    assert not IN([]).eval(None)
    assert NIN([]).eval(1)
    assert NIN([]).eval(None)


def test_named_serializers():
    class P(Person):
        @classmethod
        def age_serialize(cls, t, v):
            return f'age:{v}'  # noinspection PyUnusedLocal

    trait = P.trait('age')

    assert trait is P.trait('age')

    assert trait.serialize_value(5) == 'age:5'

    assert EQ(5).prefix_notation(field_name=trait.name, trait_dir=P.s_dir) == {'$eq': 'age:5'}

    assert BETWEEN(1, 5).prefix_notation(field_name=trait.name, trait_dir=P.s_dir) == {
        '$gte': 'age:1',
        '$lte': 'age:5',
    }

    x = OR(f(age=LE(70)), f(first_name=NE('Sasha')), f(last_name=XNone))
    assert x.prefix_notation(trait_dir=P.s_dir) == {
        '$or': [{'age': {'$lte': 'age:70'}}, {'first_name': {'$ne': 'Sasha'}}, {'last_name': {'$eq': None}}]
    }

    x = f(age=BETWEEN(50, 70), first_name=NE('Sasha'))

    assert f(x, P.s_dir).prefix_notation() == x.prefix_notation(trait_dir=P.s_dir)

    r = OR(f(age=BETWEEN(50, 70), first_name=NE('Sasha')), f(age=17))
    assert r.prefix_notation(trait_dir=P.s_dir) == {
        '$or': [
            {'$and': [{'age': {'$gte': 'age:50', '$lte': 'age:70'}}, {'first_name': {'$ne': 'Sasha'}}]},
            {'age': {'$eq': 'age:17'}},
        ]
    }


def test_f_pinned_trait_dir_takes_precedence():
    # Regression test for the precedence fix in `f.prefix_notation`:
    # a trait_dir pinned on `self` (via `f(_f, trait_dir)` or `f(..., trait_dir=...)`)
    # must take precedence over a `trait_dir` argument supplied by an
    # outer caller. This matters for nested filters like
    # `f(f(f(...), Inner.s_dir), ...)` where the inner `f` is constructed
    # for a specific class and must keep serializing against it even when
    # evaluated through an outer `prefix_notation(...)` that forwards its
    # own trait context down.
    class PA(Person):
        @classmethod
        def age_serialize(cls, t, v):
            return f'a:{v}'

    class PB(Person):
        @classmethod
        def age_serialize(cls, t, v):
            return f'b:{v}'

    pinned = f(trait_dir=PA.s_dir, age=EQ(5))

    # Pinned trait_dir wins when the caller passes a different one.
    assert pinned.prefix_notation(trait_dir=PB.s_dir) == {'age': {'$eq': 'a:5'}}

    # Pinned trait_dir is used when none is supplied by the caller.
    assert pinned.prefix_notation() == {'age': {'$eq': 'a:5'}}

    # Without a pinned trait_dir, the caller-supplied one is honored.
    bare = f(age=EQ(5))
    assert bare.prefix_notation(trait_dir=PB.s_dir) == {'age': {'$eq': 'b:5'}}

    # The pinned trait_dir is also propagated down into a nested `.filter`.
    inner = f(age=EQ(7))
    wrapped = f(inner, PA.s_dir)
    assert wrapped.prefix_notation(trait_dir=PB.s_dir) == {'age': {'$eq': 'a:7'}}

    # Field NOT forwards the field into the inner operator, so the value is still serialized.
    assert f(trait_dir=PA.s_dir, age=NOT(EQ(5))).prefix_notation() == {'$nor': [{'age': {'$eq': 'a:5'}}]}

    # Negating a wrapper keeps its pinned trait_dir for the nested filter.
    assert NOT(wrapped).prefix_notation(trait_dir=PB.s_dir) == {'$nor': [{'age': {'$eq': 'a:7'}}]}


class RefTarget(Traitable):
    key: str = T(T.ID)


class FilterTestNC(NamedConstant):
    FOO = ()
    BAR = ()


class FilterTestSubNC(FilterTestNC):
    BAZ = ()


class FilterTestFlags(EnumBits):
    READ = ()
    WRITE = ()
    EXEC = ()


# Module-level Sample so that it is properly registered as storable when used
# with real stores (DuckDbStore / MongoStore) and high-level .save().
# The Test*Filters classes still own the per-backend test methods and fixture config.
class Sample(Traitable, custom_collection=True):
    test_id: str = T(T.ID)
    i: int = T()
    f: float = T()
    b: bool = T()
    s: str = T()
    dt: datetime = T()
    d: date = T()
    opt: str = T()
    by: bytes = T()
    cl: type = T()
    lst: list = T()
    dct: dict = T()
    nc: FilterTestNC = T()
    nc2: FilterTestNC = T()
    fl: FilterTestFlags = T()
    ref: RefTarget = T()  # nullable Traitable reference; XNone serializes as JSON null


class TestCompoundFilters:
    @pytest.fixture(scope='class', autouse=True)
    def clear_store_cache(self):
        assert not TsStore.s_instances
        yield
        TsStore.s_instances.clear()

    @pytest.fixture(params=TS_STORE_TYPE.all_names())
    def prepared(self, request, live_store):
        need(
            store := live_store(store_protocol := request.param),
            f'{store_protocol} running at {test_databases.test_uri(store_protocol)} (store filter tests)',
        )

        store.begin_using()
        go = GRAPH_OFF()
        go.begin_using()

        coll_name = 'tf_' + uuid6.uuid7().hex[:12]

        data = {
            'i': 10,
            'f': 1.5,
            'b': True,
            's': 'hello',
            'dt': datetime(2024, 1, 1, tzinfo=timezone.utc),
            'd': date(2024, 6, 1),
            'by': b'hello\x00',
            'cl': Person,
            'lst': [10, 20],
            'dct': {'k': 99},
            'nc': FilterTestNC.FOO,
            'nc2': FilterTestSubNC.BAZ,
            'fl': FilterTestFlags.READ | FilterTestFlags.WRITE,
            'non_existing': '3',
        }

        overrides = {
            'i': 20,
            'f': 2,
            'b': False,
            's': 'world',
            'dt': datetime(2025, 1, 1, tzinfo=timezone.utc),
            'd': date(2025, 6, 1),
            'by': b'other',
            'cl': int,
            'lst': [99],
            'dct': {},
            'nc': FilterTestNC.BAR,
            'nc2': FilterTestSubNC.BAR,
            'fl': FilterTestFlags.EXEC,
        }

        for i in range(3):
            kw = dict(
                test_id=f's{i + 1}',
                **data,
                _collection_name=coll_name,
                _replace=True,
            )
            if not i:
                kw.update(opt='set', ref=RefTarget(key='r1'))
            if i % 2:
                kw.update(overrides)
            Sample(**kw).save().throw()

        coll = Sample.collection(_coll_name=coll_name)

        try:
            yield store, coll, data, overrides, coll_name, Sample.s_dir
        finally:
            Sample.delete_collection(coll_name, drop_history=True)
            store.end_using()
            go.end_using()

    @pytest.mark.parametrize('op', [EQ, NE])
    @pytest.mark.parametrize('trait_name', ['cl', 'lst', 'dct', 'nc', 'nc2', 'fl', 'by', 'non_existing'])
    def test_trait_prefix_and_find(self, op, trait_name, prepared):
        _store, coll, data, _overrides, _coll_name, trait_dir = prepared
        q = f(**{trait_name: op(data[trait_name])}, trait_dir=trait_dir)
        ser = t.serialize_value(data[trait_name]) if (t := Sample.trait(trait_name)) else data[trait_name]
        assert q.prefix_notation(trait_dir=trait_dir) == {trait_name: {op.label: ser}}
        res = list(coll.find(f(q, trait_dir)))
        # 3 docs total: 2 match `data[trait_name]` (s1, s3), 1 matches `overrides[trait_name]` (s2).

        expected = 0 if trait_name == 'non_existing' else 2
        if op == NE:
            expected = 3 - expected
        assert len(res) == expected
        assert coll.count(f(q, trait_dir)) == expected

        key = lambda r: str(sorted(k.items())) if isinstance((k := r.get(trait_name, XNone)), dict) else k
        assert coll.min(trait_name, f(q, trait_dir)) == (min(res, key=key) if res else None)
        assert coll.max(trait_name, f(q, trait_dir)) == (max(res, key=key) if res else None)

    def test_primitives(self, prepared):
        _store, coll, _data, _overrides, _coll_name, trait_dir = prepared
        assert len(list(coll.find(f(i=10, trait_dir=trait_dir)))) == 2
        assert len(list(coll.find(f(f=1.5, trait_dir=trait_dir)))) == 2
        assert len(list(coll.find(f(b=True, trait_dir=trait_dir)))) == 2
        assert len(list(coll.find(f(s='world', trait_dir=trait_dir)))) == 1

    def test_datetime(self, prepared):
        _store, coll, data, overrides, _coll_name, trait_dir = prepared
        assert len(list(coll.find(f(dt=overrides['dt'], trait_dir=trait_dir)))) == 1
        assert len(list(coll.find(f(dt=GT(data['dt']), trait_dir=trait_dir)))) == 1

    def test_date(self, prepared):
        _store, coll, _data, overrides, _coll_name, trait_dir = prepared
        assert len(list(coll.find(f(d=overrides['d'], trait_dir=trait_dir)))) == 1

    def test_xnone(self, prepared):
        _store, coll, _data, _overrides, _coll_name, trait_dir = prepared
        qnull = f(opt=XNone, trait_dir=trait_dir)
        nullres = list(coll.find(f(qnull, trait_dir)))
        nullids = sorted(r.get('test_id') or r.get(Nucleus.ID_TAG()) for r in nullres)
        assert nullids == ['s2', 's3']

    def test_xnone_traitable_ref(self, prepared):
        _store, coll, _data, _overrides, _coll_name, trait_dir = prepared
        q = f(ref=XNone, trait_dir=trait_dir)
        nullids = sorted(r.get('test_id') or r.get(Nucleus.ID_TAG()) for r in coll.find(f(q, trait_dir)))
        assert nullids == ['s2', 's3']

        qset = f(ref=NE(XNone), trait_dir=trait_dir)
        setids = sorted(r.get('test_id') or r.get(Nucleus.ID_TAG()) for r in coll.find(f(qset, trait_dir)))
        assert setids == ['s1']

    @pytest.mark.parametrize(
        'op, expected',
        [
            (EQ(5), ['has_x']),
            (NE(5), ['no_x']),
            (GT(3), ['has_x']),
            (GE(5), ['has_x']),
            (LT(10), ['has_x']),
            (LE(5), ['has_x']),
            (IN([5, 6]), ['has_x']),
            (NIN([5, 6]), ['no_x']),
            (BETWEEN(1, 10), ['has_x']),
        ],
        ids=['EQ', 'NE', 'GT', 'GE', 'LT', 'LE', 'IN', 'NIN', 'BETWEEN'],
    )
    def test_missing_field_semantics(self, prepared, op, expected):
        """A field entirely absent from a document: only NE/NIN match it, mirroring MongoDB's
        documented ``$ne``/``$nin`` "matches missing fields" semantics — ``NE.ibis``/``NIN.ibis``
        in trait_filter.py add the same for SQL backends (a missing blob key unwraps to NULL,
        and plain `NULL != x` would be NULL/excluded under three-valued logic without that).
        Every other operator excludes the missing field. Locks in the cross-backend contract
        after a real NE/NIN divergence was found and fixed here; runs on all three backends
        via ``prepared``, so the SQL path is covered on both DuckDB and Postgres.
        """
        store, *_ = prepared

        class MissingFieldSample(Traitable, custom_collection=True, keep_history=False):
            marker: str = T(T.ID)
            x: int = T()

        coll_name = 'mf_' + uuid6.uuid7().hex[:12]
        coll = store.collection(coll_name, MissingFieldSample.s_dir)
        try:
            coll.save_new({'_id': 'has_x', 'marker': 'has_x', 'x': 5})
            coll.save_new({'_id': 'no_x', 'marker': 'no_x'})  # x entirely absent
            ids = sorted(r['_id'] for r in coll.find(f(x=op, trait_dir=MissingFieldSample.s_dir)))
            assert ids == expected
        finally:
            store.delete_collection(coll_name)

    @pytest.mark.parametrize(
        'op, expected',
        [
            (EQ({'a': 1}), ['has_obj']),
            (EQ(None), ['has_null', 'missing']),
            (IN([{'a': 1}]), ['has_obj']),
            (NIN([{'a': 1}]), ['has_null', 'has_str', 'missing']),
            (IN([{'a': 1}, 'sss']), ['has_obj', 'has_str']),
            (IN([{'a': 1}, None]), ['has_null', 'has_obj', 'missing']),
            (IN(['sss', None]), ['has_null', 'has_str', 'missing']),
            (NIN([{'a': 1}, None]), ['has_str']),
            (IN([None]), ['has_null', 'missing']),
            (NIN([None]), ['has_obj', 'has_str']),
            (NIN(['sss']), ['has_null', 'has_obj', 'missing']),
            (IN([]), []),
            (NIN([]), ['has_null', 'has_obj', 'has_str', 'missing']),
        ],
        ids=[
            'EQ-obj',
            'EQ-None',
            'IN-obj',
            'NIN-obj',
            'IN-obj-str',
            'IN-obj-None',
            'IN-str-None',
            'NIN-obj-None',
            'IN-None',
            'NIN-None',
            'NIN-str',
            'IN-empty',
            'NIN-empty',
        ],
    )
    def test_in_nin_mixed_structure_and_null(self, prepared, op, expected):
        """``IN`` / ``NIN`` lists mixing structures, scalars and ``None`` — Mongo is the contract.

        Two traps, both verified equal on all three backends here:

        * A structure in the list routes the comparison through the native-JSON path
          (``ibis_compare_pair``), and *all* values encode that way — a JSON literal round-trips
          scalars, so a mixed list is fine. But a key stored as JSON ``null`` reads back as a
          JSON null, not SQL NULL, unless normalized — otherwise whether ``has_null`` matched
          would depend on an unrelated element of the list.
        * ``None`` cannot go into a SQL ``IN`` list at all: ``x IN (a, NULL)`` is never TRUE
          and ``x NOT IN (a, NULL)`` is never TRUE either, so it is stripped and folded back
          as an explicit NULL test (``IN._ibis_isin``). That is also what Mongo's ``$in`` /
          ``$nin`` mean by matching missing fields. Empty lists are a third case: always-false
          / always-true, not the all-None NULL check.
        """
        store, *_ = prepared

        class MixedSample(Traitable, custom_collection=True, keep_history=False):
            marker: str = T(T.ID)

        coll_name = 'mx_' + uuid6.uuid7().hex[:12]
        coll = store.collection(coll_name, MixedSample.s_dir)
        try:
            coll.save_new({'_id': 'has_obj', 'marker': 'has_obj', 'v': {'a': 1}})
            coll.save_new({'_id': 'has_str', 'marker': 'has_str', 'v': 'sss'})
            coll.save_new({'_id': 'has_null', 'marker': 'has_null', 'v': None})
            coll.save_new({'_id': 'missing', 'marker': 'missing'})  # -- v entirely absent
            assert sorted(r['_id'] for r in coll.find(f(v=op))) == expected
        finally:
            store.delete_collection(coll_name)

    def test_list_item_match_find(self, prepared):
        _store, coll, _data, _overrides, _coll_name, trait_dir = prepared
        # lst: s1, s3 = [10, 20]; s2 = [99]
        ids = lambda q: sorted(r.get('test_id') or r.get(Nucleus.ID_TAG()) for r in coll.find(f(q, trait_dir)))
        assert ids(f(lst=10, trait_dir=trait_dir)) == ['s1', 's3']
        assert ids(f(lst=NE(10), trait_dir=trait_dir)) == ['s2']
        assert ids(f(lst=IN([20, 99]), trait_dir=trait_dir)) == ['s1', 's2', 's3']
        assert ids(f(lst=NIN([99]), trait_dir=trait_dir)) == ['s1', 's3']
        assert ids(f(lst=(10, 20), trait_dir=trait_dir)) == ['s1', 's3']

    @pytest.mark.parametrize(
        ('op', 'expected'),
        [
            (10, ['float', 'int', 'mixed']),
            (2.5, ['float']),
            ('10', ['str']),
            (True, ['bool']),
            (NE(10), ['bool', 'empty', 'missing', 'none_item', 'null', 'str']),
            (NOT(EQ(10)), ['bool', 'empty', 'missing', 'none_item', 'null', 'str']),
            (IN([2.5, 'x']), ['float', 'mixed', 'str']),
            (NIN([10]), ['bool', 'empty', 'missing', 'none_item', 'null', 'str']),
            (NOT(IN([10])), ['bool', 'empty', 'missing', 'none_item', 'null', 'str']),
            (IN([2.5, (10, 20)]), ['float', 'int']),
            (NIN([2.5, (10, 20)]), ['bool', 'empty', 'missing', 'mixed', 'none_item', 'null', 'str']),
            ([10, 20], ['int']),
        ],
        ids=[
            'int',
            'float',
            'str',
            'bool',
            'NE',
            'NOT-EQ',
            'IN',
            'NIN',
            'NOT-IN',
            'IN-item-whole',
            'NIN-item-whole',
            'whole',
        ],
    )
    def test_list_item_match_edge_cases(self, prepared, op, expected):
        """Mongo is the contract: a whole number matches across int / float, and missing / null / empty hold no item."""
        store, *_ = prepared
        assert self._list_sample_ids(store, op) == expected

    @pytest.mark.parametrize(
        ('op', 'expected'),
        [
            ('builtins/int', []),
            ('builtins/str', ['str']),
            ('$v', ['str']),
            (None, ['none_item']),
            (NE('builtins/int'), ['bool', 'empty', 'float', 'int', 'missing', 'mixed', 'none_item', 'null', 'str']),
            (NE(None), ['bool', 'empty', 'float', 'int', 'missing', 'mixed', 'null', 'str']),
            (NOT(EQ('builtins/int')), ['bool', 'empty', 'float', 'int', 'missing', 'mixed', 'none_item', 'null', 'str']),
            (IN(['builtins/int', 2.5]), ['float']),
            (NIN(['builtins/int', 2.5]), ['bool', 'empty', 'int', 'missing', 'mixed', 'none_item', 'null', 'str']),
            (IN([None, 2.5]), ['float', 'none_item']),
            (NIN([None, 2.5]), ['bool', 'empty', 'int', 'missing', 'mixed', 'null', 'str']),
            (XNone, ['missing', 'null']),
            (NE(XNone), ['bool', 'empty', 'float', 'int', 'mixed', 'none_item', 'str']),
            (IN([XNone, 2.5]), ['float', 'missing', 'null']),
            (NIN([XNone, 2.5]), ['bool', 'empty', 'int', 'mixed', 'none_item', 'str']),
        ],
        ids=[
            'class-id',
            'class-id-as-item',
            'dollar-str',
            'None',
            'NE-class-id',
            'NE-None',
            'NOT-class-id',
            'IN-class-id',
            'NIN-class-id',
            'IN-None',
            'NIN-None',
            'XNone',
            'NE-XNone',
            'IN-XNone',
            'NIN-XNone',
        ],
    )
    def test_list_class_id_is_not_an_item(self, prepared, op, expected):
        store, *_ = prepared
        assert self._list_sample_ids(store, op) == expected

    @pytest.mark.parametrize(
        ('op', 'expected'),
        [
            (10, ['float', 'scalar']),
            ('x', ['str']),
            ('builtins/int', []),
            (XNone, ['missing', 'null']),
            (None, ['missing', 'null']),
            (NE(10), ['ints', 'missing', 'mixed', 'null', 'small', 'str']),
            (NOT(EQ(10)), ['ints', 'missing', 'mixed', 'null', 'small', 'str']),
            (NOT(NE(10)), ['float', 'scalar']),
            (NE('x'), ['float', 'ints', 'missing', 'mixed', 'null', 'scalar', 'small']),
            (IN([10, 'x']), ['float', 'scalar', 'str']),
            (NIN([10]), ['ints', 'missing', 'mixed', 'null', 'small', 'str']),
            (IN([XNone, 10]), ['float', 'missing', 'null', 'scalar']),
            (IN([None, 10]), ['float', 'missing', 'null', 'scalar']),
            (NIN([XNone, 10]), ['ints', 'mixed', 'small', 'str']),
        ],
        ids=[
            'int',
            'str',
            'class-id',
            'XNone',
            'None',
            'NE',
            'NOT-EQ',
            'NOT-NE',
            'NE-str',
            'IN',
            'NIN',
            'IN-XNone',
            'IN-None',
            'NIN-XNone',
        ],
    )
    def test_any_trait_has_no_item_match(self, prepared, op, expected):
        """Only list / set traits match items: an any-typed trait compares the whole value, even when it holds a list."""
        store, *_ = prepared
        assert self._whole_value_sample_ids(store, op, 'any') == expected

    def test_none_and_xnone_on_saved_traits(self, prepared):
        NoneSaved.delete_collection()
        try:
            none = NoneSaved(marker='none')
            none.n = None
            with pytest.raises(RuntimeError, match=r'NoneSaved\.n - undefined value'):
                none.save().throw()

            NoneSaved(marker='unset').save().throw()  # -- n is XNone, stored as null
            one = NoneSaved(marker='one')
            one.n, one.lst = 1, [1]
            one.save().throw()
            ids = lambda q: sorted(x.marker for x in NoneSaved.load_many(q))
            assert ids(f(n=XNone)) == ['unset']
            assert ids(f(n=None)) == ['unset']
            assert ids(f(lst=None)) == []
        finally:
            NoneSaved.delete_collection()

    def test_any_trait_matches_a_whole_list(self, prepared):
        store, *_ = prepared
        assert self._whole_value_sample_ids(store, [10, 20], 'any') == ['ints']
        assert self._whole_value_sample_ids(store, IN([10, [10, 20]]), 'any') == ['float', 'ints', 'scalar']

    @pytest.mark.parametrize('kind', ['list', 'any'])
    @pytest.mark.parametrize(
        ('op', 'expected'),
        [
            (GT(5), ['float', 'scalar']),
            (GE(10), ['float', 'scalar']),
            (LT(5), ['small']),
            (LE(3), ['small']),
            (BETWEEN(5, 9), []),
            (BETWEEN(12, 14), []),
            (BETWEEN(1, 5), ['small']),
            (GT('a'), ['str']),
            (LT('z'), ['str']),
            (NOT(GT(5)), ['ints', 'missing', 'mixed', 'null', 'small', 'str']),
            (NOT(BETWEEN(12, 14)), ['float', 'ints', 'missing', 'mixed', 'null', 'scalar', 'small', 'str']),
        ],
        ids=['GT', 'GE', 'LT', 'LE', 'BETWEEN-none', 'BETWEEN-elements', 'BETWEEN', 'GT-str', 'LT-str', 'NOT-GT', 'NOT-BETWEEN'],
    )
    def test_ordered_ops_never_look_inside_arrays(self, prepared, kind, op, expected):
        store, *_ = prepared
        assert self._whole_value_sample_ids(store, op, kind) == expected

    @staticmethod
    def _whole_value_sample_ids(store, op, kind: str) -> list:
        class AnySample(Traitable, custom_collection=True, keep_history=False):
            marker: str = T(T.ID)
            v: Any = T()

        class ListSample(Traitable, custom_collection=True, keep_history=False):
            marker: str = T(T.ID)
            v: list = T()

        cls = ListSample if kind == 'list' else AnySample
        coll_name = 'as_' + uuid6.uuid7().hex[:12]
        coll = store.collection(coll_name, cls.s_dir)
        serialize = AnySample.s_dir['v'].serialize_value
        samples = {'ints': [10, 20], 'mixed': [None, 10, 'x'], 'scalar': 10, 'float': 10.0, 'small': 3, 'str': 'x', 'null': None}
        try:
            for name, value in samples.items():
                coll.save_new({'_id': name, 'marker': name, 'v': None if value is None else serialize(value)})
            coll.save_new({'_id': 'missing', 'marker': 'missing'})
            return sorted(r['_id'] for r in coll.find(f(v=op, trait_dir=cls.s_dir)))
        finally:
            store.delete_collection(coll_name)

    def test_list_class_id_on_two_fields(self, prepared):
        store, *_ = prepared

        class TwoLists(Traitable, custom_collection=True, keep_history=False):
            marker: str = T(T.ID)
            a: list = T()
            b: list = T()

        coll_name = 'tl_' + uuid6.uuid7().hex[:12]
        coll = store.collection(coll_name, TwoLists.s_dir)
        ids = lambda q: sorted(r['_id'] for r in coll.find(q))
        try:
            coll.save_new({'_id': 'hit', 'marker': 'hit', 'a': ['builtins/str', 'x'], 'b': ['builtins/str', 'y']})
            coll.save_new({'_id': 'miss', 'marker': 'miss', 'a': ['builtins/str', 'x'], 'b': ['builtins/str', 'z']})
            assert ids(f(a='x', b='y', trait_dir=TwoLists.s_dir)) == ['hit']
            assert ids(f(a='x', b='builtins/str', trait_dir=TwoLists.s_dir)) == []
            assert ids(NOT(f(a='x', b='y', trait_dir=TwoLists.s_dir))) == ['miss']
            assert ids(OR(f(b='y', trait_dir=TwoLists.s_dir), f(b='z', trait_dir=TwoLists.s_dir))) == ['hit', 'miss']
        finally:
            store.delete_collection(coll_name)

    @staticmethod
    def _list_sample_ids(store, op) -> list:
        class ListSample(Traitable, custom_collection=True, keep_history=False):
            marker: str = T(T.ID)
            v: list = T()

        coll_name = 'ls_' + uuid6.uuid7().hex[:12]
        coll = store.collection(coll_name, ListSample.s_dir)
        try:
            coll.save_new({'_id': 'int', 'marker': 'int', 'v': ['builtins/int', 10, 20]})
            coll.save_new({'_id': 'float', 'marker': 'float', 'v': ['builtins/float', 10.0, 2.5]})
            coll.save_new({'_id': 'str', 'marker': 'str', 'v': ['builtins/str', '10', 'x', 'builtins/str', '$v']})
            coll.save_new({'_id': 'bool', 'marker': 'bool', 'v': ['builtins/bool', True]})
            coll.save_new({'_id': 'mixed', 'marker': 'mixed', 'v': [None, 10, 'x']})
            coll.save_new({'_id': 'none_item', 'marker': 'none_item', 'v': [None, None, 7]})
            coll.save_new({'_id': 'empty', 'marker': 'empty', 'v': []})
            coll.save_new({'_id': 'null', 'marker': 'null', 'v': None})
            coll.save_new({'_id': 'missing', 'marker': 'missing'})
            return sorted(r['_id'] for r in coll.find(f(v=op, trait_dir=ListSample.s_dir)))
        finally:
            store.delete_collection(coll_name)

    def test_in_and_nin(self, prepared):
        _store, coll, _data, _overrides, _coll_name, trait_dir = prepared
        assert len(list(coll.find(f(i=IN([10, 99]), trait_dir=trait_dir)))) == 2
        qmix = f(AND(f(b=True), f(i=NIN([99]))), trait_dir)
        assert len(list(coll.find(qmix))) == 2

    def test_empty_in_nin_find(self, prepared):
        _store, coll, _data, _overrides, _coll_name, trait_dir = prepared
        assert list(coll.find(f(i=IN([]), trait_dir=trait_dir))) == []
        assert len(list(coll.find(f(i=NIN([]), trait_dir=trait_dir)))) == 3
        assert len(list(coll.find(f(trait_dir=trait_dir)))) == 3

    # compounds

    def test_compound_and(self, prepared):
        _store, coll, _data, _overrides, _coll_name, trait_dir = prepared
        inner = AND(f(i=10), f(s='hello'))
        q_and = f(inner, trait_dir)
        res = list(coll.find(q_and))
        ids = sorted(r.get('test_id') or r.get(Nucleus.ID_TAG()) for r in res)
        assert ids == ['s1', 's3']
        pn_and = q_and.prefix_notation(trait_dir=trait_dir)
        assert '$and' in pn_and or len(pn_and) > 0

    def test_compound_or(self, prepared):
        _store, coll, _data, _overrides, _coll_name, trait_dir = prepared
        q_or = f(OR(f(i=10), f(i=20)), trait_dir)
        res = list(coll.find(q_or))
        ids = sorted(r.get('test_id') or r.get(Nucleus.ID_TAG()) for r in res)
        assert ids == ['s1', 's2', 's3']

    def test_not_find(self, prepared):
        """NOT matches a missing field, same as Mongo ``$not``.

        ``NOT(OR(...))`` lowers to an AND of field NOTs before it reaches the store.
        """
        store, *_ = prepared

        class TextSample(Traitable, custom_collection=True, keep_history=False):
            marker: str = T(T.ID)
            s: str = T()
            x: int = T()

        coll_name = 'not_' + uuid6.uuid7().hex[:12]
        trait_dir = TextSample.s_dir
        coll = store.collection(coll_name, trait_dir)
        try:
            coll.save_new({'_id': 'hello', 'marker': 'hello', 's': 'hello', 'x': 10})
            coll.save_new({'_id': 'world', 'marker': 'world', 's': 'world', 'x': 3})
            coll.save_new({'_id': 'nulls', 'marker': 'nulls', 's': None, 'x': None})
            coll.save_new({'_id': 'missing', 'marker': 'missing'})

            def ids(query):
                return sorted(r['_id'] for r in coll.find(query))

            assert ids(f(s=NOT(EQ('hello')), trait_dir=trait_dir)) == ['missing', 'nulls', 'world']
            assert ids(f(x=NOT(GT(5)), trait_dir=trait_dir)) == ['missing', 'nulls', 'world']
            assert ids(f(x=NOT(NE(10)), trait_dir=trait_dir)) == ['hello']
            assert ids(f(x=NOT(BETWEEN(1, 5)), trait_dir=trait_dir)) == ['hello', 'missing', 'nulls']
            assert ids(NOT(OR(f(s='hello', trait_dir=trait_dir), f(x=GT(5), trait_dir=trait_dir)))) == ['missing', 'nulls', 'world']

            # Top-level match-nothing, alone, nested, and as the negation of an empty AND().
            assert ids(OR()) == []
            assert ids(f(OR(), x=GT(5), trait_dir=trait_dir)) == []
            assert ids(NOT(f(AND(), x=GT(5), trait_dir=trait_dir))) == ['missing', 'nulls', 'world']
            # A match-all arm keeps the whole OR match-all.
            assert ids(OR(f(x=GT(5), trait_dir=trait_dir), f())) == ['hello', 'missing', 'nulls', 'world']
            assert ids(NOT(f(OR(), x=GT(5), trait_dir=trait_dir))) == ['hello', 'missing', 'nulls', 'world']
            assert ids(NOT(f(x=IN([]), trait_dir=trait_dir))) == ['hello', 'missing', 'nulls', 'world']
            assert ids(NOT(f(x=IN([]), s='hello', trait_dir=trait_dir))) == ['hello', 'missing', 'nulls', 'world']
        finally:
            store.delete_collection(coll_name)


def test_not_eval_and_prefix():
    sasha = Person(first_name='Sasha', last_name='Davidovich', age=40)
    ann = Person(first_name='Ann', last_name='Davidovich', age=3)

    assert NOT(GT(5)).eval(5)
    assert not NOT(GT(5)).eval(6)
    assert NOT(GT(5)).prefix_notation() == {'$not': {'$gt': 5}}
    assert NOT(BETWEEN(1, 2)).prefix_notation() == {'$not': {'$gte': 1, '$lte': 2}}
    assert NOT(NOT(GT(5))).prefix_notation() == {'$gt': 5}
    assert NOT(IN([])).prefix_notation() == {'$not': {'$in': []}}

    assert NOT(f(age=2)).eval(ann)
    assert not NOT(f(age=3)).eval(ann)
    assert NOT(f(age=2)).prefix_notation() == {'$nor': [{'age': {'$eq': 2}}]}
    both = f(age=GT(5), first_name='Ann')
    assert NOT(both).prefix_notation() == OR(f(age=NOT(GT(5))), f(first_name=NOT(EQ('Ann')))).prefix_notation()
    assert NOT(OR(f(age=GT(5)), f(first_name='Ann'))).prefix_notation() == AND(f(age=NOT(GT(5))), f(first_name=NOT(EQ('Ann')))).prefix_notation()
    assert NOT(NOT(f(age=GT(5)))).prefix_notation() == f(age=GT(5)).prefix_notation()
    assert both.eval(sasha) is False and NOT(NOT(both)).eval(sasha) is False
    assert both.eval(Person(first_name='Ann', last_name='Davidovich', age=10))
    assert NOT(NOT(both)).eval(Person(first_name='Ann', last_name='Davidovich', age=10))

    assert NOT(OR()).prefix_notation() == {}
    assert NOT(OR()).eval(ann)
    assert NOT(f()).prefix_notation() == {'$expr': False}
    assert not NOT(f()).eval(ann)
    assert NOT(AND()).prefix_notation() == {'$expr': False}
    assert NOT(f(x=IN([]))).prefix_notation() == {'$nor': [{'x': {'$in': []}}]}
    assert NOT(f(AND(), age=GT(5))).prefix_notation() == {'$or': [{'$nor': [{'age': {'$gt': 5}}]}, {'$expr': False}]}
    assert OR(f(age=GT(5)), f()).prefix_notation() == {}
    assert NOT(f(OR(), age=GT(5))).prefix_notation() == {}
    assert NOT(f(OR(), age=GT(5))).eval(sasha)
