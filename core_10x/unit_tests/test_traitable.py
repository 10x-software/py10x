import unittest

from core_10x.code_samples.person import Person
from core_10x.trait_definition import RT, T
from core_10x.traitable import Traitable
from core_10x.traitable_id import ID
from core_10x.ts_union import TsUnion

class SubTraitable(Traitable):
    s_special_attributes = ('special_attr',)
    trait1: int = T()
    trait2: str = RT()

    x = '123' #not in slots

class TestTraitableSlots(unittest.TestCase):

    def test_traitable_slots(self):
        expected_slots = ('T', '_default_cache', '_rev', '_collection_name')
        self.assertEqual(Traitable.__slots__, expected_slots)

    def test_subclass_slots(self):
        expected_slots = ('special_attr',) + Traitable.__slots__ + ('trait1', 'trait2')
        self.assertEqual(SubTraitable.__slots__, expected_slots)

    def test_instance_slots(self):
        with TsUnion():
            instance = SubTraitable()
        with self.assertRaises(AttributeError):
            instance.non_existent_attr = 'value'


class TestTraitable(unittest.TestCase):

    def test_init_with_id(self):
        pid = ID('John|Smith',False)
        p = Person(_id=pid)
        self.assertEqual(p.id(), pid)

    def test_init_with_trait_values(self):
        with TsUnion():
            p = Person(first_name='John', last_name='Smith')
        self.assertEqual(p.first_name, 'John')
        self.assertEqual(p.last_name, 'Smith')

    def test_set_values(self):
        with TsUnion():
            p = Person(first_name='John', last_name='Smith')
        rc = p.set_values(age=19, weight_lb=200)
        self.assertTrue(rc)


