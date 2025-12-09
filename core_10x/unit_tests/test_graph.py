from __future__ import annotations

import functools
from weakref import WeakKeyDictionary

import pytest
from core_10x.code_samples.person import WEIGHT_QU, Person
from core_10x.exec_control import BTP, CACHE_ONLY, GRAPH_OFF, GRAPH_ON, INTERACTIVE
from core_10x.trait_definition import RT, T
from core_10x.traitable import Traitable
from core_10x.traitable_id import ID
from core_10x.xnone import XNone


def call_counter(method):
    @functools.wraps(method)
    def ctr(self, *args, **kwargs):
        ctr.call_counts[self] = ctr.call_counts.get(self, 0) + 1
        return method(self, *args, **kwargs)

    ctr.call_counts = WeakKeyDictionary()
    ctr.call_count = lambda obj: ctr.call_counts.get(obj, 0) if obj else sum(ctr.call_counts.values())
    return ctr


class CallCount:
    def __init__(self, obj, method):
        self.obj = obj
        self.method = method
        assert hasattr(method, 'call_count')

    def __enter__(self):
        self.method.call_counts[self.obj] = 0
        return self

    def __exit__(self, *args):
        pass

    @property
    def call_count(self):
        return self.method.call_count(self.obj)


class TestablePerson(Person):
    older_than_get = call_counter(Person.older_than_get)
    weight_get = call_counter(Person.weight_get)
    weight_set = call_counter(Person.weight_set)

    young: bool = RT()

    @call_counter
    def young_get(self) -> bool:
        return self.age < 30

    @classmethod
    def load_data(cls, id: ID) -> dict | None:
        return None


@pytest.fixture
def testable_person():
    with CACHE_ONLY():
        return TestablePerson(first_name='John', last_name='Smith')


def reset_person(p):
    for trait in p.s_dir.values():
        if not trait.getter_params:
            p.invalidate_value(trait)
            if not trait.flags_on(T.ID):  # id traits may be set in base layer
                if trait.f_get.__name__ == 'default_value':  # TODO: replace with flags
                    assert p.get_value(trait) is trait.default, trait.name
                elif trait.f_get.__name__.endswith('_get'):
                    assert p.get_value(trait) == getattr(p, f'{trait.name}_get')()
                else:
                    assert p.get_value(trait) == trait.f_get(p)
        else:
            # TODO: use nodes?
            ...


def test_get_set(testable_person):
    on = BTP.current().flags() & BTP.ON_GRAPH
    p = testable_person
    p.weight_lbs = 100.0
    p.weight_qu = WEIGHT_QU.LB

    assert p.weight == 100

    with CallCount(p, TestablePerson.weight_get) as cc:
        assert p.weight == 100
        assert cc.call_count == (not on)

    p.weight_qu = WEIGHT_QU.KG
    assert p.weight_qu is WEIGHT_QU.KG

    with CallCount(p, TestablePerson.weight_get) as cc:
        assert p.weight == 100 / WEIGHT_QU.KG.value
        assert cc.call_count == 1

    # now use the setter...
    with CallCount(p, TestablePerson.weight_set) as cc:
        p.weight = 100.0
        assert cc.call_count == 1

    with CallCount(p, TestablePerson.weight_get) as cc:
        assert p.weight == 100
        assert cc.call_count == 1

    with CallCount(p, TestablePerson.weight_get) as cc:
        assert p.weight_lbs == 100 * WEIGHT_QU.KG.value
        assert cc.call_count == 0


def test_dep_change(testable_person):
    on = BTP.current().flags() & BTP.ON_GRAPH
    p = testable_person
    p.age = 30

    assert not p.young

    with CallCount(p, TestablePerson.young_get) as cc:
        assert not p.young
        assert cc.call_count == (not on)

    p.age = 20
    with CallCount(p, TestablePerson.young_get) as cc:
        assert p.young
        assert cc.call_count == 1

    p.age = 30


def test_dep_change_with_arg(testable_person):
    on = BTP.current().flags() & BTP.ON_GRAPH

    p = testable_person
    p.age = 30

    assert not p.older_than(30)

    with CallCount(p, TestablePerson.older_than_get) as cc:
        assert not p.older_than(30)
        assert cc.call_count == (not on)

    p.age = 40
    with CallCount(p, TestablePerson.older_than_get) as cc:
        assert p.older_than(30)
        assert cc.call_count == 1

    p.age = 30


@pytest.fixture
def graph_on_person():
    graph_on = GRAPH_ON()
    graph_on.begin_using()
    with CACHE_ONLY():
        p = TestablePerson(first_name='Jane', last_name='Smith')
    pid = p.id()
    p.age = 30
    yield p, pid, graph_on
    # Cleanup
    assert p.age == 30
    graph_on.end_using()
    assert p.first_name is XNone
    assert p.last_name is XNone
    assert p.weight_lbs is XNone
    assert p.age is p.age_get()
    assert p.id() == pid


def test_nested(graph_on_person):
    p, _pid, _graph_on = graph_on_person
    assert p.full_name == 'Jane Smith'
    with INTERACTIVE() as i1:
        p.last_name = 'Baker'
        assert p.full_name == 'Jane Baker'
        with INTERACTIVE() as i2:
            p.first_name = 'Tom'
            assert p.full_name == 'Tom Baker'
        assert p.full_name == 'Jane Baker'
        with i2:
            assert p.full_name == 'Tom Baker'
        assert p.full_name == 'Jane Baker'

    assert p.full_name == 'Jane Smith'
    with i1:
        assert p.full_name == 'Jane Baker'

    assert p.full_name == 'Jane Smith'


def test_convert(testable_person, on=False):
    assert on == bool(BTP.current().flags() & BTP.CONVERT_VALUES)
    if not on:
        with pytest.raises(TypeError):
            Person(first_name=1, last_name=2)
    else:
        p = Person(first_name=1, last_name=2)
        assert p.full_name == '1 2'


def test_graph(testable_person, on=False):
    assert on == bool(BTP.current().flags() & BTP.ON_GRAPH)
    test_dep_change(testable_person)
    test_dep_change_with_arg(testable_person)
    test_get_set(testable_person)


def test_exec_control(testable_person, graph=False, convert=False, debug=False):
    with CACHE_ONLY():
        test_graph(testable_person, on=graph)
        reset_person(testable_person)
        test_convert(testable_person, on=convert)
        reset_person(testable_person)
        if not convert:
            test_debug(testable_person, on=debug)


def test_repro(testable_person):
    with GRAPH_ON():
        testable_person.weight_lbs = 100
        reset_person(testable_person)
        with GRAPH_OFF():
            testable_person.weight_lbs = 100
            reset_person(testable_person)


def test_graph_on(testable_person):
    with GRAPH_ON():
        test_exec_control(testable_person, True, False, False)
        with GRAPH_OFF():
            test_exec_control(testable_person, False, False, False)
            reset_person(testable_person)


def test_debug(testable_person, on=False):
    assert on == bool(BTP.current().flags() & BTP.DEBUG)
    p = TestablePerson(first_name='John', last_name='Smith')
    assert p.weight_lbs is XNone

    p.weight_lbs = 100.0

    if on:
        with pytest.raises(TypeError):
            p.weight_lbs = '200'

        assert p.weight == 100.0

    p.weight_lbs = 200
    assert p.weight == 200.0

    p.invalidate_value(p.T.weight_lbs)
    assert p.weight_lbs is XNone


def test_graph_convert_debug(testable_person):
    with GRAPH_ON(convert_values=True, debug=True):
        test_exec_control(testable_person, True, True, True)
        with GRAPH_OFF():
            test_exec_control(testable_person, False, True, True)
        with GRAPH_OFF(convert_values=False):
            test_exec_control(testable_person, False, False, True)
        with GRAPH_OFF(debug=False, convert_values=False):
            test_exec_control(testable_person, False, False, False)


def test_graph_convert(testable_person):
    with GRAPH_ON(convert_values=True):
        test_exec_control(testable_person, True, True, False)
        with GRAPH_OFF():
            test_exec_control(testable_person, False, True, False)
        with GRAPH_OFF(convert_values=False):
            test_exec_control(testable_person, False, False, False)
        with GRAPH_OFF(debug=True, convert_values=False):
            test_exec_control(testable_person, False, False, True)


def test_graph_debug(testable_person):
    with GRAPH_ON(debug=True):
        test_exec_control(testable_person, True, False, True)

        with GRAPH_OFF():
            test_exec_control(testable_person, False, False, True)
        with GRAPH_OFF(debug=False):
            test_exec_control(testable_person, False, False, False)
        with GRAPH_OFF(debug=False, convert_values=True):
            test_exec_control(testable_person, False, True, False)


@pytest.mark.parametrize('on_graph', [0, 1])
@pytest.mark.parametrize('debug', [0, 1])
@pytest.mark.parametrize('convert_values', [0, 1])
@pytest.mark.parametrize('on_graph2', [0, 1])
@pytest.mark.parametrize('debug2', [0, 1])
@pytest.mark.parametrize('convert_values2', [0, 1])
def test_traitable_processor_creation(on_graph, debug, convert_values, on_graph2, debug2, convert_values2):
    class X(Traitable):
        x: int = RT(T.ID)
        v: int = RT()

    X(x=1, v=10)
    assert X(x=1).v == 10

    default_cache = BTP.current().cache()
    with BTP.create(on_graph, debug, convert_values, use_parent_cache=False, use_default_cache=False):
        X(x=2, v=20)
        parent_cache = BTP.current().cache()
        assert default_cache is not parent_cache
        with BTP.create(on_graph2, debug2, convert_values2, use_parent_cache=False, use_default_cache=False):
            X(x=3, v=30)
            child_cache = BTP.current().cache()
            assert child_cache is not parent_cache
            assert child_cache is not default_cache
            assert X(x=1).v == 10
            assert X(x=2).v == 20

        with BTP.create(on_graph2, debug2, convert_values2, use_parent_cache=True, use_default_cache=False):
            X(x=4, v=40)
            child_cache = BTP.current().cache()
            if on_graph == on_graph2:  # use_parent_cache only works if both parent and child are either on_graph or off_graph
                assert child_cache is parent_cache
            else:
                assert child_cache is not parent_cache
                assert child_cache is not default_cache
        with BTP.create(on_graph2, debug2, convert_values2, use_parent_cache=False, use_default_cache=True):
            X(x=5, v=50)
            child_cache = BTP.current().cache()
            if not on_graph2:  # use_default_cache only works for off-graph mode
                assert child_cache is default_cache
                assert X(x=2).v is XNone
            else:
                assert child_cache is not parent_cache
                assert child_cache is not default_cache
                assert X(x=2).v == 20  # from parent
            assert X(x=1).v == 10

        assert X(x=1).v == 10  # from parent caches
        assert X(x=2).v == 20  # set in this cache
        assert X(x=3).v is XNone  # not set as was set in child with use_parent_cache=False
        if on_graph == on_graph2:  # use_parent_cache only works if both parent and child are either on_graph or off_graph
            assert X(x=4).v == 40  # this cache, as was set in child with use_parent_cache=True
        if not on_graph2:  # use_default_cache only works for off-graph mode
            assert X(x=5).v == 50  # in default cache, which is our parent

    assert X(x=1).v == 10
    assert X(x=2).v is XNone
    assert X(x=3).v is XNone
    assert X(x=4).v is XNone
    if not on_graph2:  # use_default_cache only works for off-graph mode
        assert X(x=5).v == 50  # we are in default cache, and it was set in default cache

    # TODO assert behavior with conflicting params, e.g.
    #
    # with pytest.raises(Exception):
    #     BTP.create(-1,-1,-1,use_parent_cache=True,use_default_cache=True)

    # TODO: node set, cleared, checked - each in nested cache level
