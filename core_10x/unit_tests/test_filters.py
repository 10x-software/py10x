from __future__ import annotations

from datetime import date, datetime, timezone

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
    GE,
    GT,
    IN,
    LE,
    LT,
    NE,
    NIN,
    NOT_EMPTY,
    OR,
    f,
)
from core_10x.traitable import Traitable, XNone
from core_10x.ts_store import TsStore
from core_10x.ts_store_type import TS_STORE_TYPE


class Person(Traitable):
    first_name: str
    last_name: str
    age: int
    dob: date


def test_filters():
    p = Person(first_name='Sasha', last_name='Davidovich')

    r = OR(f(age=BETWEEN(50, 70), first_name=NE('Sasha')), f(age=17))

    assert r.prefix_notation() == {'$or': [{'age': {'$gte': 50, '$lte': 70}, 'first_name': {'$ne': 'Sasha'}}, {'age': {'$eq': 17}}]}
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
    assert r6.prefix_notation() == {'$in': []}

    assert not r1.eval(p)
    assert r2.eval(p)
    assert r3.eval(p)
    assert not r4.eval(p)
    assert r5.eval(p)
    assert not r6.eval(p)

    r7 = OR(OR(), OR())
    assert r7.prefix_notation() == {'$in': []}
    assert not r7.eval(p)

    r8 = OR(OR(), AND())
    assert r7.prefix_notation() == {'$in': []}
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
    assert r8.prefix_notation() == {'$in': []}
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
    assert OR().prefix_notation() == {'$in': []}
    assert AND().prefix_notation() == {}


def test_f_named_expressions_eval_and_prefix():
    d = Person(age=10, first_name='Bob', last_name='')

    # named expressions may be raw values (wrapped to EQ) or filters
    filt = f(age=EQ(10), first_name='Bob')
    assert filt.eval(d)
    assert filt.prefix_notation() == {'age': {'$eq': 10}, 'first_name': {'$eq': 'Bob'}}

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
            {'age': {'$gte': 'age:50', '$lte': 'age:70'}, 'first_name': {'$ne': 'Sasha'}},
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
