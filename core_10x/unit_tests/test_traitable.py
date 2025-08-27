import unittest

from core_10x.code_samples.person import Person
from core_10x.trait_definition import RT, T, M
from core_10x.traitable import Traitable
from core_10x.traitable_id import ID
from core_10x.ts_union import TsUnion

class SubTraitable(Traitable):
    s_special_attributes = ('special_attr',)
    trait1: int = RT()
    trait2: str = RT()

    x = '123' #not in slots

class SubTraitable2(SubTraitable):
    trait2: int = M()
    trait3: float

class SubTraitable3(SubTraitable):
    trait2: list[str]

class TestTraitableTraits(unittest.TestCase):

    def test_subclass_traits(self):
        expected_traits = {'trait1', 'trait2'}
        self.assertEqual({t.name for t in SubTraitable.traits(flags_off=T.RESERVED)}, expected_traits)

    def test_subclass2_traits(self):
        expected_traits = {'trait1', 'trait2', 'trait3'}
        self.assertEqual({t.name for t in SubTraitable2.traits(flags_off=T.RESERVED)}, expected_traits)
        assert SubTraitable.trait('trait2').data_type == str
        assert SubTraitable2.trait('trait2').data_type == int
        assert SubTraitable3.trait('trait2').data_type == list

    def test_is_storable(self):
        self.assertFalse(SubTraitable.is_storable())
        self.assertTrue(SubTraitable2.is_storable())

        with self.assertRaisesRegex(OSError,'No Store is available'):
            SubTraitable2().save()

        assert 'is not storable' in SubTraitable().save().error()

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


