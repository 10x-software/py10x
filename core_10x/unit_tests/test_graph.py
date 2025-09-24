import functools
from unittest import TestCase
from weakref import WeakKeyDictionary

from core_10x.code_samples.person import WEIGHT_QU, Person
from core_10x.exec_control import BTP, GRAPH_OFF, GRAPH_ON, INTERACTIVE
from core_10x.trait_definition import RT, T
from core_10x.ts_union import TsUnion
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


class TestGraphBase(TestCase):
    def setUp(self):
        with TsUnion():
            self.p = TestablePerson(first_name='John', last_name='Smith')

    def tearDown(self):
        self.reset()

    def reset(self):
        for trait in self.p.s_dir.values():
            if not trait.getter_params:
                self.p.invalidate_value(trait)
                if not trait.flags_on(T.ID):  # id traits may be set in base layer
                    if trait.f_get.__name__ == 'default_value':  # TODO: replace with flags
                        self.assertIs(self.p.get_value(trait), trait.default, trait.name)
                    elif trait.f_get.__name__.endswith('_get'):
                        self.assertEqual(self.p.get_value(trait), getattr(self.p, f'{trait.name}_get')())
                    else:
                        self.assertEqual(self.p.get_value(trait), trait.f_get(self.p))
            else:
                # TODO: use nodes?
                ...

    def test_get_set(self):
        on = BTP.current().flags() & BTP.ON_GRAPH
        p = self.p
        p.weight_lbs = 100.0
        p.weight_qu = WEIGHT_QU.LB

        self.assertEqual(p.weight, 100)

        with CallCount(p, TestablePerson.weight_get) as cc:
            self.assertEqual(p.weight, 100)
            self.assertEqual(cc.call_count, not on)

        p.weight_qu = WEIGHT_QU.KG
        self.assertIs(p.weight_qu, WEIGHT_QU.KG)

        with CallCount(p, TestablePerson.weight_get) as cc:
            self.assertEqual(p.weight, 100 / WEIGHT_QU.KG.value)
            self.assertEqual(cc.call_count, 1)

        # now use the setter...
        with CallCount(p, TestablePerson.weight_set) as cc:
            p.weight = 100.0
            self.assertEqual(cc.call_count, 1)

        with CallCount(p, TestablePerson.weight_get) as cc:
            self.assertEqual(p.weight, 100)
            self.assertEqual(cc.call_count, 1)

        with CallCount(p, TestablePerson.weight_get) as cc:
            self.assertEqual(p.weight_lbs, 100 * WEIGHT_QU.KG.value)
            self.assertEqual(cc.call_count, 0)

    def test_dep_change(self):
        on = BTP.current().flags() & BTP.ON_GRAPH
        p = self.p
        p.age = 30

        self.assertFalse(p.young)

        with CallCount(p, TestablePerson.young_get) as cc:
            self.assertFalse(p.young)
            self.assertEqual(cc.call_count, not on)

        p.age = 20
        with CallCount(p, TestablePerson.young_get) as cc:
            self.assertTrue(p.young)
            self.assertEqual(cc.call_count, 1)

        p.age = 30

    def test_dep_change_with_arg(self):
        on = BTP.current().flags() & BTP.ON_GRAPH

        p = self.p
        p.age = 30

        self.assertFalse(p.older_than(30))

        with CallCount(p, TestablePerson.older_than_get) as cc:
            self.assertFalse(p.older_than(30))
            self.assertEqual(cc.call_count, not on)

        p.age = 40
        with CallCount(p, TestablePerson.older_than_get) as cc:
            self.assertTrue(p.older_than(30))
            self.assertEqual(cc.call_count, 1)

        p.age = 30


class TestGraphOn(TestGraphBase):
    def setUp(self):
        self.graph_on = GRAPH_ON()
        self.graph_on.begin_using()
        with TsUnion():
            self.p = TestablePerson(first_name='Jane', last_name='Smith')
        self.pid = self.p.id()
        self.p.age = 30

    def reset(self):
        # no need to reset as it resets upon exiting the graph_on context (tested in tearDown)
        pass

    def tearDown(self):
        self.assertEqual(self.p.age, 30)
        self.graph_on.end_using()

        self.assertIs(self.p.first_name, XNone)
        self.assertIs(self.p.last_name, XNone)
        self.assertIs(self.p.weight_lbs, XNone)
        self.assertIs(self.p.age, self.p.age_get())
        self.assertEqual(self.p.id(), self.pid)

    def test_nested(self):
        p = self.p
        self.assertEqual(p.full_name, 'Jane Smith')
        with INTERACTIVE() as i1:
            p.last_name = 'Baker'
            self.assertEqual(p.full_name, 'Jane Baker')
            with INTERACTIVE() as i2:
                p.first_name = 'Tom'
                self.assertEqual(p.full_name, 'Tom Baker')
            self.assertEqual(p.full_name, 'Jane Baker')
            with i2:
                self.assertEqual(p.full_name, 'Tom Baker')
            self.assertEqual(p.full_name, 'Jane Baker')

        self.assertEqual(p.full_name, 'Jane Smith')
        with i1:
            self.assertEqual(p.full_name, 'Jane Baker')

        self.assertEqual(p.full_name, 'Jane Smith')


class TestExecControl(TestGraphBase):
    def test_convert(self, on=False):
        self.assertEqual(on, bool(BTP.current().flags() & BTP.CONVERT_VALUES))
        if not on:
            with self.assertRaises(TypeError):
                Person(first_name=1, last_name=2)
        else:
            p = Person(first_name=1, last_name=2)
            self.assertEqual(p.full_name, '1 2')

    def test_graph(self, on=False):
        self.assertEqual(on, bool(BTP.current().flags() & BTP.ON_GRAPH))
        self.test_dep_change()
        self.test_dep_change_with_arg()
        self.test_get_set()

    def test(self, graph=False, convert=False, debug=False):
        with TsUnion():
            self.test_graph(on=graph)
            self.reset()
            self.test_convert(on=convert)
            self.reset()
            if not convert:
                self.test_debug(on=debug)

    def test_repro(self):
        with GRAPH_ON():
            self.p.weight_lbs = 100
            self.reset()
            with GRAPH_OFF():
                self.p.weight_lbs = 100
                self.reset()

    def test_graph_on(self):
        with GRAPH_ON():
            self.test(True, False, False)
            with GRAPH_OFF():
                self.test(False, False, False)
                self.reset()

    def test_debug(self, on=False):
        self.assertEqual(on, bool(BTP.current().flags() & BTP.DEBUG))
        p = TestablePerson(first_name='John', last_name='Smith')
        self.assertIs(p.weight_lbs, XNone)

        p.weight_lbs = 100.0

        if on:
            with self.assertRaises(TypeError):
                p.weight_lbs = '200'

            self.assertEqual(p.weight, 100.0)

        p.weight_lbs = 200
        self.assertEqual(p.weight, 200.0)

        p.invalidate_value(p.T.weight_lbs)
        self.assertIs(p.weight_lbs, XNone)

    def test_graph_convert_debug(self):
        with GRAPH_ON(convert_values=True, debug=True):
            self.test(True, True, True)
            with GRAPH_OFF():
                self.test(False, True, True)
            with GRAPH_OFF(convert_values=False):
                self.test(False, False, True)
            with GRAPH_OFF(debug=False, convert_values=False):
                self.test(False, False, False)

    def test_graph_convert(self):
        with GRAPH_ON(convert_values=True):
            self.test(True, True, False)
            with GRAPH_OFF():
                self.test(False, True, False)
            with GRAPH_OFF(convert_values=False):
                self.test(False, False, False)
            with GRAPH_OFF(debug=True, convert_values=False):
                self.test(False, False, True)

    def test_graph_debug(self):
        with GRAPH_ON(debug=True):
            self.test(True, False, True)

            with GRAPH_OFF():
                self.test(False, False, True)
            with GRAPH_OFF(debug=False):
                self.test(False, False, False)
            with GRAPH_OFF(debug=False, convert_values=True):
                self.test(False, True, False)
