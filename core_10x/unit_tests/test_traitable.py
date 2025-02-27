import unittest

from core_10x.code_samples.person import Person
from core_10x.trait_definition import RT, T
from core_10x.traitable import Traitable

class SubTraitable(Traitable):
    s_special_attributes = ('special_attr',)
    trait1: int = T()
    trait2: str = RT()

    x = '123' #not in slots

class TestTraitableSlots(unittest.TestCase):

    def test_traitable_slots(self):
        expected_slots = ('trait', '_default_cache', '_rev')
        self.assertEqual(Traitable.__slots__, expected_slots)

    def test_subclass_slots(self):
        expected_slots = ('special_attr', 'trait', '_default_cache', '_rev', 'trait1', 'trait2')
        self.assertEqual(SubTraitable.__slots__, expected_slots)

    def test_instance_slots(self):
        instance = SubTraitable()
        with self.assertRaises(AttributeError):
            instance.non_existent_attr = 'value'


class TestTraitable(unittest.TestCase):

    def test_init_with_id(self):
        p = Person(_id='John|Smith')
        self.assertEqual(p.id(), 'John|Smith')

    def test_init_with_trait_values(self):
        p = Person(first_name='John', last_name='Smith')
        self.assertEqual(p.first_name, 'John')
        self.assertEqual(p.last_name, 'Smith')

    def test_set_values(self):
        p = Person(first_name='John', last_name='Smith')
        rc = p.set_values(age=19, weight_lb=200)
        self.assertTrue(rc)


if __name__ == '__main__':
    unittest.main()