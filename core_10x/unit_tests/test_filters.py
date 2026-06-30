from __future__ import annotations

from datetime import date, datetime, timezone
import uuid

import pytest

from core_10x.exec_control import GRAPH_OFF
from core_10x.named_constant import EnumBits, NamedConstant
from core_10x.testlib.strict import need
from core_10x.nucleus import Nucleus
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
from infra_10x.duckdb_store import DuckDbStore
from infra_10x.mongodb_store import MongoStore


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


def test_named_serializers():
    class P(Person):
        @classmethod
        def age_serialize(cls, t, v):
            return f'age:{v}'  # noinspection PyUnusedLocal

    trait = P.trait('age')

    assert trait is P.trait('age')

    assert trait.serialize_value(5) == 'age:5'

    assert EQ(5).prefix_notation(field_name=trait.name, traitable_class=P.s_bclass) == {'$eq': 'age:5'}

    assert BETWEEN(1, 5).prefix_notation(field_name=trait.name, traitable_class=P.s_bclass) == {
        '$gte': 'age:1',
        '$lte': 'age:5',
    }

    x = OR(f(age=LE(70)), f(first_name=NE('Sasha')), f(last_name=XNone))
    assert x.prefix_notation(traitable_class=P.s_bclass) == {
        '$or': [{'age': {'$lte': 'age:70'}}, {'first_name': {'$ne': 'Sasha'}}, {'last_name': {'$eq': None}}]
    }

    x = f(age=BETWEEN(50, 70), first_name=NE('Sasha'))

    assert f(x, P.s_bclass).prefix_notation() == x.prefix_notation(traitable_class=P.s_bclass)

    r = OR(f(age=BETWEEN(50, 70), first_name=NE('Sasha')), f(age=17))
    assert r.prefix_notation(traitable_class=P.s_bclass) == {
        '$or': [
            {'age': {'$gte': 'age:50', '$lte': 'age:70'}, 'first_name': {'$ne': 'Sasha'}},
            {'age': {'$eq': 'age:17'}},
        ]
    }


def test_f_pinned_traitable_class_takes_precedence():
    # Regression test for the precedence fix in `f.prefix_notation`:
    # a traitable_class pinned on `self` (via `f(_f, _t)` or `f(..., _t=...)`)
    # must take precedence over a `traitable_class` argument supplied by an
    # outer caller. This matters for nested filters like
    # `f(f(f(...), Inner.s_bclass), ...)` where the inner `f` is constructed
    # for a specific class and must keep serializing against it even when
    # evaluated through an outer `prefix_notation(...)` that forwards its
    # own class context down.
    class PA(Person):
        @classmethod
        def age_serialize(cls, t, v):
            return f'a:{v}'

    class PB(Person):
        @classmethod
        def age_serialize(cls, t, v):
            return f'b:{v}'

    pinned = f(_t=PA.s_bclass, age=EQ(5))

    # Pinned class wins when the caller passes a different class.
    assert pinned.prefix_notation(traitable_class=PB.s_bclass) == {'age': {'$eq': 'a:5'}}

    # Pinned class is used when no class is supplied by the caller.
    assert pinned.prefix_notation() == {'age': {'$eq': 'a:5'}}

    # Without a pinned class, the caller-supplied class is honored.
    bare = f(age=EQ(5))
    assert bare.prefix_notation(traitable_class=PB.s_bclass) == {'age': {'$eq': 'b:5'}}

    # The pinned class is also propagated down into a nested `.filter`.
    inner = f(age=EQ(7))
    wrapped = f(inner, PA.s_bclass)
    assert wrapped.prefix_notation(traitable_class=PB.s_bclass) == {'age': {'$eq': 'a:7'}}


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
    ref: RefTarget = T()   # nullable Traitable reference; XNone serializes as JSON null


class TestCompoundFilters:
    s_mongo_running = True
    @pytest.fixture(scope='class', autouse=True)
    def clear_store_cache(self):
        assert not TsStore.s_instances
        yield
        TsStore.s_instances.clear()

    @pytest.fixture(
        params=[
            lambda: DuckDbStore.instance(),
            lambda: MongoStore.instance(hostname='mongodb://localhost:27017/', dbname='test_filters_mongo', sst=100),
        ],
        ids=['duckdb', 'mongodb'],
    )
    def prepared(self, request):
        is_mongo_store = request.param_index == 1
        store = None
        try:
            if not is_mongo_store or self.s_mongo_running:
                store = request.param()
        except Exception:
            if is_mongo_store:
                self.s_mongo_running = False
            else:
                raise
        if is_mongo_store:
            need(self.s_mongo_running, 'MongoDB running (mongo-store filter tests)')

        store.begin_using()
        go = GRAPH_OFF()
        go.begin_using()

        coll_name = 'tf_' + uuid.uuid4().hex[:12]

        data = dict(
            i=10,
            f=1.5,
            b=True,
            s='hello',
            dt=datetime(2024, 1, 1, tzinfo=timezone.utc),
            d=date(2024, 6, 1),
            by=b'hello\x00',
            cl=Person,
            lst=[10, 20],
            dct={'k': 99},
            nc=FilterTestNC.FOO,
            nc2=FilterTestSubNC.BAZ,
            fl=FilterTestFlags.READ | FilterTestFlags.WRITE,
        )

        overrides = dict(
            i=20,
            f=2,
            b=False,
            s='world',
            dt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            d=date(2025, 6, 1),
            by=b'other',
            cl=int,
            lst=[99],
            dct={},
            nc=FilterTestNC.BAR,
            nc2=FilterTestSubNC.BAR,
            fl=FilterTestFlags.EXEC,
        )

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
            yield store, coll, data, overrides, coll_name, Sample.s_bclass
        finally:
            store.delete_collection(coll_name)
            store.end_using()
            go.end_using()

    @pytest.mark.parametrize('trait_name', ['cl', 'lst', 'dct', 'nc', 'nc2', 'fl', 'by'])
    def test_trait_prefix_and_find(self, trait_name, prepared):
        _store, coll, data, _overrides, _coll_name, bclass = prepared
        q = f(**{trait_name: data[trait_name]}, _t=bclass)
        ser = Sample.trait(trait_name).serialize_value(data[trait_name])
        assert q.prefix_notation(traitable_class=bclass) == {trait_name: {'$eq': ser}}
        assert len(list(coll.find(f(q, bclass)))) == 2

    def test_primitives(self, prepared):
        _store, coll, _data, _overrides, _coll_name, bclass = prepared
        assert len(list(coll.find(f(i=10, _t=bclass)))) == 2
        assert len(list(coll.find(f(f=1.5, _t=bclass)))) == 2
        assert len(list(coll.find(f(b=True, _t=bclass)))) == 2
        assert len(list(coll.find(f(s='world', _t=bclass)))) == 1

    def test_datetime(self, prepared):
        _store, coll, data, overrides, _coll_name, bclass = prepared
        assert len(list(coll.find(f(dt=overrides['dt'], _t=bclass)))) == 1
        assert len(list(coll.find(f(dt=GT(data['dt']), _t=bclass)))) == 1

    def test_date(self, prepared):
        _store, coll, _data, overrides, _coll_name, bclass = prepared
        assert len(list(coll.find(f(d=overrides['d'], _t=bclass)))) == 1

    def test_xnone(self, prepared):
        _store, coll, _data, _overrides, _coll_name, bclass = prepared
        qnull = f(opt=XNone, _t=bclass)
        nullres = list(coll.find(f(qnull, bclass)))
        nullids = sorted(r.get('test_id') or r.get(Nucleus.ID_TAG()) for r in nullres)
        assert nullids == ['s2', 's3']

    def test_xnone_traitable_ref(self, prepared):
        _store, coll, _data, _overrides, _coll_name, bclass = prepared
        q = f(ref=XNone, _t=bclass)
        nullids = sorted(r.get('test_id') or r.get(Nucleus.ID_TAG()) for r in coll.find(f(q, bclass)))
        assert nullids == ['s2', 's3']

        qset = f(ref=NE(XNone), _t=bclass)
        setids = sorted(r.get('test_id') or r.get(Nucleus.ID_TAG()) for r in coll.find(f(qset, bclass)))
        assert setids == ['s1']

    def test_in_and_nin(self, prepared):
        _store, coll, _data, _overrides, _coll_name, bclass = prepared
        assert len(list(coll.find(f(i=IN([10, 99]), _t=bclass)))) == 2
        qmix = f(AND(f(b=True), f(i=NIN([99]))), bclass)
        assert len(list(coll.find(qmix))) == 2

    # compounds

    def test_compound_and(self, prepared):
        _store, coll, _data, _overrides, _coll_name, bclass = prepared
        inner = AND(f(i=10), f(s='hello'))
        q_and = f(inner, bclass)
        res = list(coll.find(q_and))
        ids = sorted(r.get('test_id') or r.get(Nucleus.ID_TAG()) for r in res)
        assert ids == ['s1', 's3']
        pn_and = q_and.prefix_notation(traitable_class=bclass)
        assert '$and' in pn_and or len(pn_and) > 0

    def test_compound_or(self, prepared):
        _store, coll, _data, _overrides, _coll_name, bclass = prepared
        q_or = f(OR(f(i=10), f(i=20)), bclass)
        res = list(coll.find(q_or))
        ids = sorted(r.get('test_id') or r.get(Nucleus.ID_TAG()) for r in res)
        assert ids == ['s1', 's2', 's3']
