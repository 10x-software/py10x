import uuid

import pytest
from core_10x.code_samples.person import Person
from core_10x.exec_control import CACHE_ONLY
from core_10x.trait_definition import RT, M, T
from core_10x.traitable import Traitable
from core_10x.traitable_id import ID
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

    assert Y.is_storable()
    assert Y.trait('_collection_name')

    y = Y(_collection_name='test')

    assert y.id().collection_name == 'test'
    assert y._collection_name == 'test'
