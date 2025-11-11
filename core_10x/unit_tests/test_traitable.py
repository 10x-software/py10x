from __future__ import annotations

import collections
import uuid
from datetime import date

import pytest
from core_10x.code_samples.person import Person
from core_10x.exec_control import BTP, CACHE_ONLY
from core_10x.trait_definition import RT, M, T
from core_10x.traitable import THIS_CLASS, Traitable
from core_10x.traitable_id import ID
from core_10x.xnone import XNone
from core_10x_i import BFlags


class SubTraitable(Traitable):
    s_special_attributes = ('special_attr',)
    trait1: int = RT(T.ID)
    trait2: str = RT()

    x = '123'  # -- not in slots


class SubTraitable2(SubTraitable):
    trait1 = M(flags=(BFlags(0), T.ID))  # removes ID flag
    trait2: int = M()
    trait3: float = T() // 'trait definition comment'
    trait4: int = RT(0)


class SubTraitable3(SubTraitable):
    trait2: list[str] = M() // 'trait modification comment'


def test_subclass_traits():
    expected_traits = {'trait1', 'trait2'}
    assert {t.name for t in SubTraitable.traits(flags_off=T.RESERVED)} == expected_traits


def test_subclass2_traits():
    expected_traits = ['trait1', 'trait2', 'trait3', 'trait4']
    assert [t.name for t in SubTraitable2.traits(flags_off=T.RESERVED)] == expected_traits
    assert SubTraitable.trait('trait2').data_type is str
    assert SubTraitable2.trait('trait2').data_type is int
    assert SubTraitable3.trait('trait2').data_type is list
    assert SubTraitable2.trait('trait4').default_value() == 0
    assert SubTraitable2.trait('trait2').ui_hint.tip == 'Trait2'
    assert SubTraitable2.trait('trait3').ui_hint.tip == 'trait definition comment'
    assert SubTraitable3.trait('trait2').ui_hint.tip == 'trait modification comment'


def test_is_storable():
    assert not SubTraitable.is_storable()
    assert SubTraitable2.is_storable()

    with pytest.raises(OSError, match='No Store is available'):
        SubTraitable2().save()

    assert 'is not storable' in SubTraitable(trait1=uuid.uuid1().int).save().error()


def test_trait_update():
    with CACHE_ONLY():
        instance = SubTraitable(trait1=10, trait2='hello')
        assert instance.trait2 == 'hello'

        assert instance == SubTraitable.update(trait1=10, trait2='world')
        assert instance.trait2 == 'world'

        assert instance == SubTraitable.update(trait1=10, trait2=None)  # setting to None
        assert instance.trait2 is None


def test_traitable_slots():
    expected_slots = ('T', '_default_cache', '_rev', '_collection_name')
    assert Traitable.__slots__ == expected_slots


def test_subclass_slots():
    expected_slots = ('special_attr', *Traitable.__slots__, 'trait1', 'trait2')
    assert SubTraitable.__slots__ == expected_slots


def test_instance_slots():
    with CACHE_ONLY():
        instance = SubTraitable(trait1=10)
    with pytest.raises(AttributeError):
        instance.non_existent_attr = 'value'


def test_init_with_id():
    pid = ID('John|Smith')
    p = Person(pid)
    assert p.id() == pid


def test_init_with_trait_values():
    with CACHE_ONLY():
        p = Person(first_name='John', last_name='Smith')
    assert p.first_name == 'John'
    assert p.last_name == 'Smith'


def test_set_values():
    with CACHE_ONLY():
        p = Person(first_name='John', last_name='Smith')
    rc = p.set_values(age=19, weight_lb=200)
    assert rc


def test_dynamic_traits():
    class X(Traitable):
        s_own_trait_definitions = dict(x=RT(data_type=int, get=lambda self: 10))

    x = X()
    assert x.T.x.data_type is int
    assert x.x == 10

    class Y(X):
        y: int = RT(20)

    y = Y()
    assert y.T.x.data_type is int
    assert y.x == 10

    assert y.T.y.data_type is int
    assert y.y == 20


def test_collection_name_trait():
    class X(Traitable):
        x: int

    assert not X.is_storable()
    assert not X.trait('_collection_name')

    class Y(Traitable):
        s_default_trait_factory = T
        s_custom_collection = True
        y: int

        @classmethod
        def load_data(cls, id: ID) -> dict | None:
            return None

    assert Y.is_storable()
    assert Y.trait('_collection_name')

    y = Y(_collection_name='test')

    assert y.id().collection_name == 'test'
    assert y._collection_name == 'test'


@pytest.mark.parametrize('on_graph', [0, 1])
@pytest.mark.parametrize('debug', [0, 1])
@pytest.mark.parametrize('convert_values', [0, 1])
@pytest.mark.parametrize('use_parent_cache', [True, False])
@pytest.mark.parametrize('use_default_cache', [True, False])
@pytest.mark.parametrize('use_existing_instance_by_id', [True, False])
@pytest.mark.parametrize('self_ref', [True, False])
def test_traitable_ref_load(on_graph, debug, convert_values, use_parent_cache, use_default_cache, use_existing_instance_by_id, self_ref):
    load_calls = collections.Counter()

    class X(Traitable):
        i: int = T(T.ID)
        x: THIS_CLASS = T()

        @classmethod
        def exists_in_store(cls, id: ID) -> bool:
            return id.value == '1'

        @classmethod
        def load_data(cls, id: ID) -> dict | None:
            v = id.value
            load_calls[v] += 1
            i = int(v)
            return {'_id': v, 'i': i, '_rev': 1} | ({'x': {'_id': str(i + int(not self_ref))}} if i < 3 else {})

    with BTP.create(on_graph, convert_values, debug, use_parent_cache, use_default_cache):
        x = X.existing_instance_by_id(ID('1')) if use_existing_instance_by_id else X.existing_instance(i=1)
        x1 = X(i=3, x=x)
        assert x1.x is x
        assert not load_calls

        assert x.i == 1
        expected = lambda n: {str(i): 1 + int(debug and self_ref) for i in range(1, n + 1)}
        if debug and not self_ref:
            assert load_calls == expected(3)
            assert x.x.x == x1  # found existing instance
            assert x1.x is XNone  # reload in debug mode
        else:
            assert load_calls == expected(1)
            assert x.x
            assert not self_ref or x == x.x
            assert load_calls == expected(1)
            assert x.x.i == 1 + int(not self_ref)
            assert load_calls == expected(1 + int(not self_ref))
            assert x.x.x == (x if self_ref else x1)  # found existing instance
            assert x1.x is x  # no reload

    # TODO: change flags; as_of context


def test_trait_methods():
    class A(Traitable):
        t: int

    class B(A):
        def t_get(self):
            return 1

    class C(B):
        t: str = M()
        def t_get(self):
            return 2

    class D(C):
        t: date = M()

    for t, dt in zip([A,B,C,D],[int,int,str,date],strict=True):
        assert t.trait('t').data_type is dt

    for t, v in zip([A,B,C,D],[XNone,1,2,2],strict=True):
        assert t().t is v
