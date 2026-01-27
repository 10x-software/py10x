from __future__ import annotations

import collections
import contextlib
import re
import uuid
from collections import Counter
from contextlib import nullcontext
from datetime import date
from typing import TYPE_CHECKING, Any, Self

import numpy as np
import pytest
from core_10x import trait_definition
from core_10x.code_samples.person import Person
from core_10x.exec_control import BTP, CACHE_ONLY, GRAPH_ON, INTERACTIVE
from core_10x.rc import RC, RC_TRUE
from core_10x.trait import Trait
from core_10x.trait_definition import RT, M, T, TraitDefinition
from core_10x.trait_method_error import TraitMethodError
from core_10x.traitable import THIS_CLASS, AnonymousTraitable, Traitable, TraitAccessor
from core_10x.traitable_id import ID
from core_10x.xnone import XNone
from core_10x_i import BFlags

if TYPE_CHECKING:
    from collections.abc import Generator


class SubTraitable(Traitable):
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

    with pytest.raises(OSError, match='No Traitable Store is specified: neither explicitly, nor via backbone or URI'):
        SubTraitable2().save()

    assert 'is not storable' in SubTraitable(trait1=uuid.uuid1().int).save().error()


def test_trait_update():
    with CACHE_ONLY():
        instance = SubTraitable(trait1=10, trait2='hello', _replace=True)
        assert instance.trait2 == 'hello'

        assert instance == SubTraitable.update(trait1=10, trait2='world')
        assert instance.trait2 == 'world'

        assert instance == SubTraitable.update(trait1=10, trait2=None)  # setting to None
        assert instance.trait2 is None


def test_instance_slots():
    assert Traitable.__slots__ == ()
    assert SubTraitable.__slots__ == ()
    instance = SubTraitable(trait1=10)
    assert not hasattr(instance, '__dict__')
    with pytest.raises(AttributeError):
        instance.non_existent_attr = 'value'


def test_init_with_id():
    with GRAPH_ON():  # isolate lazy reference so it does not affect other tests
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
        s_own_trait_definitions = dict(x=RT(data_type=int, default=10))

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
@pytest.mark.parametrize('nested', [True, False])
def test_traitable_ref_load(on_graph, debug, convert_values, use_parent_cache, use_default_cache, use_existing_instance_by_id, self_ref, nested):
    load_calls = collections.Counter()

    class X(Traitable):
        i: int = T(T.ID)
        x: THIS_CLASS = T()
        y: int = T()

        @classmethod
        def exists_in_store(cls, id: ID) -> bool:
            return id.value == '1'

        @classmethod
        def load_data(cls, id: ID) -> dict | None:
            v = id.value
            load_calls[v] += 1
            i = int(v)
            return {'_id': v, 'i': i, '_rev': 1, 'y': 1} | ({'x': {'_id': str(i + int(not self_ref))}} if i < 3 else {})

    with BTP.create(on_graph, convert_values, debug, use_parent_cache, use_default_cache):
        x = X.existing_instance_by_id(ID('1')) if use_existing_instance_by_id else X.existing_instance(i=1)
        assert x
        x1 = X(i=3, x=x, y=2, _replace=True)
        assert x1.x is x
        assert x1.y == 2  # still 2 as lazy-load occurs before setting parameters passed
        assert load_calls == {'3': 1}  # lazy-load since no db access in constructor
        load_calls.clear()

        assert x.i == 1
        expected = lambda n: {str(i): 1 for i in range(1, n + 1)}
        if debug and not self_ref:
            assert load_calls == expected(3)
            assert x.x.x == x1  # found existing instance
            assert x1.x is XNone  # reload in debug mode
        else:
            with BTP.create(-1, -1, -1, use_parent_cache=False, use_default_cache=False) if nested else nullcontext():
                assert load_calls == expected(1)
                assert x.x
                assert not self_ref or x == x.x
                assert load_calls == expected(1)
                assert x.x.i == 1 + int(not self_ref)
                assert load_calls == expected(1 + int(not self_ref))
                assert x.x.x == (x if self_ref else x1)  # found existing instance
                assert x1.x is x  # no reload

    # TODO: change_flags; as_of context
    # TODO: nodes with args...


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

        @classmethod
        def load_data(cls, id):
            return None

    class Z(Y):
        x: AnonymousTraitable = M(T.EMBEDDED)

    x = X(a=1)
    assert x.serialize(True) == {'a': 1}

    y = Y(y=0, x=x, _replace=True)
    with pytest.raises(
        TraitMethodError, match=r"test_anonymous_traitable.<locals>.X - anonymous' instance may not be serialized as external reference"
    ):
        y.serialize_object()

    z = Z(y=1, x=x, _replace=True)
    s = z.serialize_object()
    assert s['x'] == {'_obj': {'a': 1}, '_type': '_nx', '_cls': 'test_traitable/test_anonymous_traitable/<locals>/X'}

    z = Z(y=2, x=Y(y=3), _replace=True)
    with pytest.raises(TraitMethodError, match=r'test_anonymous_traitable.<locals>.Y/3 - embedded instance must be anonymous'):
        z.serialize_object()


def test_own_trait_defs():
    cnt = Counter()

    def assert_and_cont(what, obj, arg, trait=None):
        assert isinstance(obj, Traitable)
        if trait:
            assert isinstance(trait, Trait)
            assert trait.data_type is int
            assert trait.flags_on(T.RUNTIME | T.EXPENSIVE)
        cnt[what] += arg

    class X(Traitable):
        def x_get(self, arg) -> int:
            assert_and_cont('get', self, arg)
            return 1

        def x_set(self, trait, value, arg) -> RC:
            assert_and_cont('set', self, arg, trait)
            self.raw_set_value(trait, value + 1, arg)
            return RC_TRUE

        @classmethod
        def own_trait_definitions(cls) -> Generator[tuple[str, trait_definition.TraitDefinition]]:
            yield 'x', TraitDefinition(T.RUNTIME | T.EXPENSIVE, data_type=int)

    t = X.trait('x')
    assert cnt == {}
    x = X()
    assert x.x(1) == 1
    assert cnt == {'get': 1}

    x.set_value(t, 2, 1)
    assert x.x(1) == 3
    assert cnt == {'get': 1, 'set': 1}


def test_trait_get_default_override():
    class X(Traitable):
        x: int = RT(default=1)

    assert X().x == 1

    with pytest.raises(
        RuntimeError,
        match=r'Ambiguous definition for x_get on <class \'test_traitable.test_trait_get_default_override.<locals>.Y\'> - both trait.default and traitable.x_get are defined.',
    ):

        class Y(X):
            x: int = RT(default=2)

            def x_get(self):
                return 2

    class Z(X):
        def x_get(self):
            return 3

    class T(Z):
        def x_get(self):
            return 4

    class S(T):
        x: int = RT(default=5)

    assert Z().x == 3
    assert T().x == 4
    assert S().x == 5


def test_create_and_share():
    class X(Traitable):
        x: int = RT(T.ID)
        y: int = RT(T.ID)
        z: int = RT()
        t: int = RT(T.ID_LIKE)

        def y_get(self):
            return self.t

    with pytest.raises(TypeError, match=re.escape('test_create_and_share.<locals>.X expects at least one ID trait value')):
        X()

    with pytest.raises(TypeError, match=re.escape("test_create_and_share.<locals>.X.y (<class 'int'>) - invalid value ''")):
        X(x=1)

    X(x=1, y=1, z=1, _replace=True)

    with pytest.raises(ValueError, match=re.escape('test_create_and_share.<locals>.X.z - non-ID trait value cannot be set during initialization')):
        X(x=1, y=1, z=2)

    with pytest.raises(ValueError, match=re.escape('test_create_and_share.<locals>.X.z - non-ID trait value cannot be set during initialization')):
        X(x=1, y=1, z=1)

    with pytest.raises(ValueError, match=re.escape('test_create_and_share.<locals>.X.z - non-ID trait value cannot be set during initialization')):
        X(x=1, t=1, z=1)

    assert X(x=1, t=1).z == 1
    assert X(x=1, y=1).z == 1

    with INTERACTIVE():
        x = X()  # empty object allowed - OK!
        z = X(x=1, y=1)
        assert z.z == 1  # found from parent

        x.x = 1
        x.y = 1
        assert not x.share(False)
        assert x.z is XNone


def test_serialize():
    save_calls = Counter()
    history_save_calls = Counter()
    load_calls = Counter()
    serialized = {}

    class X(Traitable):
        x: int = T(T.ID)
        y: Self = T()
        z: int = T()

        @classmethod
        def exists_in_store(cls, id: ID) -> bool:
            return id.value in serialized or int(id.value) > 3

        @classmethod
        def load_data(cls, id: ID) -> dict | None:
            load_calls[id.value] += 1
            return serialized.get(id.value)

        @classmethod
        def store(cls):
            class Store:
                def auth_user(self):
                    return 'test_user'

                def collection(self, collection_name):
                    class Collection:
                        def create_index(self, name, trait_name):
                            return name

                        def save(self, serialized_data):
                            if not collection_name.endswith('#history'):
                                id_value = serialized_data['_id']
                                save_calls[id_value] += 1
                            else:
                                id_value = serialized_data['$set']['_id']
                                history_save_calls[id_value] += 1

                            serialized[id_value] = serialized_data
                            return 1

                        save_new = save

                    return Collection()

            return Store()

        def z_get(self) -> int:
            return self.y._rev if self.y and self.y._rev else 0

    class Y(X): ...

    x = X(x=0)
    assert not serialized
    x.save().throw()
    assert not load_calls
    assert dict(save_calls) == {'0': 1}
    assert dict(history_save_calls) == {next(iter(history_save_calls)): 1}
    assert serialized['0']['z'] == 0
    save_calls.clear()
    load_calls.clear()

    x = X(x=1, y=X(x=2, y=X(x=1), _replace=True), _replace=True)
    x.save()
    assert save_calls == {'1': 1}
    assert load_calls == {str(i): 1 for i in range(1, 3)}
    save_calls.clear()
    load_calls.clear()

    x.save(save_references=True)
    assert save_calls == {'1': 1, '2': 1}
    assert load_calls == {}
    save_calls.clear()

    X(x=3, y=Y(_id=ID('4')), z=0, _replace=True).save(save_references=True)
    assert load_calls == {'3': 1}
    assert save_calls == {'3': 1}  # save of a lazy load is noop

    assert X(x=3).y.__class__ is Y
    with pytest.raises(
        TraitMethodError,
        match=re.escape(
            "Failed in <class 'test_traitable.test_serialize.<locals>.X'>.z.z_get\n    object = 5;\n    value = ()\n    args = test_serialize.<locals>.X/6: object reference not found in store"
        ),
    ):
        X(x=5, y=X(_id=ID('6')), _replace=True).save(save_references=True)


def test_id_trait_set():
    class X(Traitable):
        x: int = RT(T.ID)
        y: int = RT(T.ID_LIKE)

    with INTERACTIVE():
        x = X()
        x.x = 1
        x.y = 1
        assert x.x == 1
        x.x = 2
        assert x.x == 2

        x.share(False)
        with pytest.raises(ValueError, match=r"test_id_trait_set.<locals>.X.x \(<class 'int'>\) - cannot change ID trait value from '2' to '3'"):
            x.x = 3
        assert x.x == 2  # not updated on shared object
        x.x = 2  # same value works..

        with pytest.raises(ValueError, match=r"test_id_trait_set.<locals>.X.y \(<class 'int'>\) - cannot change ID_LIKE trait value from '1' to '4'"):
            x.y = 4
        assert x.y == 1
        x.y = 1  # same value works..

    x = X(x=1)
    with pytest.raises(ValueError, match=r"test_id_trait_set.<locals>.X.x \(<class 'int'>\) - cannot change ID trait value from '1' to '2'"):
        x.x = 2
    assert x.x == 1  # not updated on shared object
    x.x = 1  # same value works..


def test_reload():
    rev = 0

    class X(Traitable):
        x: int = T(T.ID)

        @classmethod
        def load_data(cls, id: ID) -> dict | None:
            nonlocal rev
            rev += 1
            data = {'_id': id.value, 'x': int(id.value), '_rev': rev}
            return data

    # reload of lazy ref
    x = X(ID('1'))
    x.reload()
    assert x._rev == 1

    x.reload()
    assert x._rev == 2

    x = X(ID('2'))
    with GRAPH_ON():
        x.reload()
        assert x._rev == 3
        assert rev == 3
    assert x._rev == 3
    assert rev == 3

    x = X(ID('3'))
    with GRAPH_ON():
        y = X(ID('3'))
        assert y._rev == 4
    assert x._rev == 4


def test_separation():
    class X(Traitable):
        x: int = RT(T.ID)
        y: int = RT()

    with GRAPH_ON() as g1:
        x1 = X(x=1, y=1, _replace=True)

    with GRAPH_ON() as g2:
        x2 = X(x=1, y=2, _replace=True)

    assert X(x=1).y is XNone

    with g1:
        assert X(x=1).y == 1
        with pytest.raises(RuntimeError, match=r'X/1: object not usable - origin cache is not reachable'):
            x2.get_value('y')

    with g2:
        assert X(x=1).y == 2
        with pytest.raises(RuntimeError, match=r'X/1: object not usable - origin cache is not reachable'):
            x1.get_value('y')

    with pytest.raises(RuntimeError, match=r'X/1: object not usable - origin cache is not reachable'):
        x1.get_value('y')

    with pytest.raises(RuntimeError, match=r'X/1: object not usable - origin cache is not reachable'):
        x2.get_value('y')


@pytest.mark.parametrize('value', [{'x': 1}, {}, [], [1], np.float64(1.1)])
def test_any_trait(value):
    class X(Traitable):
        x: int = T(T.ID)
        y: Any = T()
        z: list = T()

        @classmethod
        def load_data(cls, id: ID) -> dict | None:
            return None

    with GRAPH_ON():
        x = X(x=1, y=value, z=[value], _replace=True)
        assert x.y == value
        assert x.z[0] == value
        assert type(x.y) is type(value)
        assert type(x.z[0]) is type(value)
        s = x.serialize_object()

    with GRAPH_ON():
        x = X.deserialize_object(x.s_bclass, None, s)
        assert x.y == value
        assert x.z[0] == value
        assert type(x.y) is type(value)
        assert type(x.z[0]) is type(value)
        assert s == x.serialize_object()


@pytest.mark.parametrize('t', [T, RT])
def test_exceptions(t):
    class X(Traitable):
        x: int = t(T.ID)
        y: int = t(default=1)

    with CACHE_ONLY():
        with (
            pytest.raises(
                RuntimeError,
                match=r'test_exceptions.<locals>.X/1: object construction failed for lazy reference to non-storable that does not exist in memory',
            )
            if t is RT
            else contextlib.nullcontext()
        ):
            x = X(_id=ID('1'))
            with (
                pytest.raises(RuntimeError, match=r'test_exceptions.<locals>.X/1: object reference not found in store')
                if t is T
                else contextlib.nullcontext()
            ):
                assert x.y == 1


def test_multiple_inheritance():
    """Test universal multiple inheritance with __slots__=() and MRO resolution"""

    # Test 1: Basic multiple inheritance works
    class EntityA(Traitable):
        name: str = RT(T.ID)
        value: int = RT()

        def value_get(self) -> int:
            return 42

    class EntityB(Traitable):
        rev: int = RT(T.ID)
        value: str = RT()

        def value_get(self) -> str:
            return 'forty two'

    class Combined(EntityA, EntityB):
        extra: str = RT()

    assert EntityA.__slots__ == ()
    assert EntityB.__slots__ == ()
    assert Combined.__slots__ == ()

    # Verify MRO
    mro_names = [cls.__name__ for cls in Combined.__mro__]
    assert mro_names[:4] == ['Combined', 'EntityA', 'EntityB', 'Traitable']

    obj = Combined(name='test', rev=1)

    assert obj.name == 'test'
    assert obj.value == 42
    assert obj.rev == 1

    assert isinstance(obj.T, TraitAccessor)
    assert obj.T.name.data_type is str
    assert obj.T.value.data_type is int
    assert obj.T.rev.data_type is int
