from __future__ import annotations

import collections
import re
import uuid
from collections import Counter
from contextlib import nullcontext
from datetime import date
from typing import TYPE_CHECKING

import pytest
from core_10x import trait_definition
from core_10x.code_samples.person import Person
from core_10x.exec_control import BTP, CACHE_ONLY, INTERACTIVE
from core_10x.rc import RC, RC_TRUE
from core_10x.trait import Trait
from core_10x.trait_definition import RT, M, T, TraitDefinition
from core_10x.trait_method_error import TraitMethodError
from core_10x.traitable import THIS_CLASS, AnonymousTraitable, Traitable
from core_10x.traitable_id import ID
from core_10x.xnone import XNone
from core_10x_i import BFlags

if TYPE_CHECKING:
    from collections.abc import Generator


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
    expected_slots = ('T', '_default_cache')
    assert Traitable.__slots__ == expected_slots
    assert not hasattr(Traitable(),'__dict__')

def test_subclass_slots():
    expected_slots = ('special_attr', *Traitable.__slots__)
    assert SubTraitable.__slots__ == expected_slots
    assert not hasattr(SubTraitable(trait1=1),'__dict__')

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
@pytest.mark.parametrize('nested', [True,False])
def test_traitable_ref_load(on_graph, debug, convert_values, use_parent_cache, use_default_cache, use_existing_instance_by_id, self_ref,nested):
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
            with BTP.create(-1,-1,-1,use_parent_cache=False,use_default_cache=False) if nested else nullcontext():
                assert load_calls == expected(1)
                assert x.x
                assert not self_ref or x == x.x
                assert load_calls == expected(1)
                assert x.x.i == 1 + int(not self_ref)
                assert load_calls == expected(1 + int(not self_ref))
                assert x.x.x == (x if self_ref else x1)  # found existing instance
                assert x1.x is x  # no reload

    #TODO: change_flags; as_of context
    #TODO: nodes with args...


def test_trait_methods():
    class A(Traitable):
        s_default_trait_factory = T
        t: int

        @classmethod
        def exists_in_store(cls, id):
            return False

        @classmethod
        def load_data(cls, id):
            return None

    class B(A):
        def t_get(self):
            return 1

        @classmethod
        def t_serialize(cls, trait, value):
            return value + 1

    class C(B):
        t: str = M()

        def t_get(self):
            return 2

        @classmethod
        def t_serialize(cls, trait, value):
            return value + 2

    class D(C):
        t: date = M()

    for t, dt in zip([A, B, C, D], [int, int, str, date], strict=True):
        assert t.trait('t').data_type is dt

    for t, v in zip([A, B, C, D], [XNone, 1, 2, 2], strict=True):
        assert t().t is v
        assert t().serialize_object()['t'] == (v * 2 or None)


def test_anonymous_traitable():
    class X(AnonymousTraitable):
        a: int = T()

    class Y(Traitable):
        y: int = T(T.ID)
        x: Traitable = T()

        @classmethod
        def exists_in_store(cls, id):
            return False

    class Z(Y):
        x: AnonymousTraitable = M(T.EMBEDDED)

    x = X(a=1)
    assert x.serialize(True) == {'a': 1}

    y = Y(y=0, x=x)
    with pytest.raises(
        TraitMethodError, match=r"test_anonymous_traitable.<locals>.X - anonymous' instance may not be serialized as external reference"
    ):
        y.serialize_object()

    z = Z(y=1, x=x)
    s = z.serialize_object()
    assert s['x'] == {'a': 1}

    z = Z(y=2, x=Y(y=3))
    with pytest.raises(TraitMethodError, match=r'test_anonymous_traitable.<locals>.Y/3 - embedded instance must be anonymous'):
        z.serialize_object()


def test_own_trait_defs_and_override():
    cnt = Counter()

    def assert_and_cont(what, obj, arg, trait=None):
        assert isinstance(obj, Traitable)
        if trait:
            assert isinstance(trait, Trait)
            assert trait.data_type is int
            assert trait.flags_on(T.RUNTIME | T.EXPENSIVE)
        cnt[what] += arg

    class X(Traitable):
        @staticmethod
        def own_trait_definitions(
            bases: tuple, inherited_trait_dir: dict, class_dict: dict, rc: RC
        ) -> Generator[tuple[str, trait_definition.TraitDefinition]]:
            def get(self, arg) -> int:
                assert_and_cont('get', self, arg)
                return 1

            def set(self, trait, value, arg) -> RC:
                assert_and_cont('set', self, arg, trait)
                self.raw_set_value(trait, value + 1, arg)
                return RC_TRUE

            yield 'x', TraitDefinition(T.RUNTIME | T.EXPENSIVE, data_type=int, get=get, set=set)

    t = X.trait('x')
    assert list(t.t_def.params.keys()) == ['get', 'set']
    assert cnt == {}
    x = X()
    assert x.x(1) == 1
    assert cnt == {'get': 1}

    x.set_value(t, 2, 1)
    assert x.x(1) == 3
    assert cnt == {'get': 1, 'set': 1}


def test_trait_func_override():
    class X(Traitable):
        x: int = RT(get=lambda self: 1)

    assert X().x == 1

    with pytest.raises(
        RuntimeError,
        match=r'Ambiguous definition for x_get on <class \'test_traitable.test_trait_func_override.<locals>.Y\'> - both trait.get and traitable.x_get are defined.',
    ):

        class Y(X):
            x: int = RT(get=lambda self: 2)
            def x_get(self):
                return 2

    class Z(X):
        def x_get(self):
            return 3

    class T(Z):
        def x_get(self):
            return 4

    class S(T):
        x: int = RT(get=lambda self: 5)

    assert Z().x == 3
    assert T().x == 4
    assert S().x == 5


def test_create_and_share():
    class X(Traitable):
        x: int = RT(T.ID)
        y: int = RT(T.ID)
        z: int = RT()
        t: int = RT()
        def y_get(self):
            return self.t

    with pytest.raises(TypeError, match=re.escape('test_create_and_share.<locals>.X expects at least one ID trait value')):
        X()

    with pytest.raises(TypeError, match=re.escape("test_create_and_share.<locals>.X.y (<class 'int'>) - invalid value ''")):
        X(x=1)


    X(x=1,y=1,z=1)

    with pytest.raises(ValueError, match=re.escape("test_create_and_share.<locals>.X/1|1 - already exists with potentially different non-ID trait values")):
        X(x=1,y=1,z=2)

    with pytest.raises(ValueError, match=re.escape("test_create_and_share.<locals>.X/1|1 - already exists with potentially different non-ID trait values")):
        X(x=1,y=1,z=1)

    with pytest.raises(
        ValueError, match=re.escape('test_create_and_share.<locals>.X/1|1 - already exists with potentially different non-ID trait values')
    ):
        X(x=1, t=1, z=1)

    #assert X(x=1,t=1).z == 1 #TODO: should this succeed?
    assert X(x=1, y=1).z == 1

    with INTERACTIVE():
        x = X() # empty object allowed - OK!
        y = X() # partial id not allowed
        z = X(x=1,y=1) # works here!
        assert z.z == 1 # found from parent

        x.x =1
        x.y =1
        x.share(False)
        assert x.z == 1

        y.x = 1
        y.y = 1
        y.z = 2
        y.share(False) ## TODO: should this fail?
        assert x.z == 1 ## TODO: ignored?
