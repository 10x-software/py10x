from __future__ import annotations

from datetime import date  # noqa: TC003

import pytest
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

    assert EQ(5).prefix_notation(trait=trait, traitable_class=P.s_bclass) == {'$eq': 'age:5'}

    assert BETWEEN(1, 5).prefix_notation(trait=trait, traitable_class=P.s_bclass) == {
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
