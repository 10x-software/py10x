import unittest
import uuid

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


class TestTraitableTraits(unittest.TestCase):
    def test_subclass_traits(self):
        expected_traits = {'trait1', 'trait2'}
        self.assertEqual({t.name for t in SubTraitable.traits(flags_off=T.RESERVED)}, expected_traits)

    def test_subclass2_traits(self):
        expected_traits = ['trait1', 'trait2', 'trait3', 'trait4']
        assert [t.name for t in SubTraitable2.traits(flags_off=T.RESERVED)] == expected_traits
        assert SubTraitable.trait('trait2').data_type is str
        assert SubTraitable2.trait('trait2').data_type is int
        assert SubTraitable3.trait('trait2').data_type is list
        assert SubTraitable2.trait('trait4').default_value() == 0
        assert SubTraitable2.trait('trait2').ui_hint.tip == 'Trait2'
        assert SubTraitable2.trait('trait3').ui_hint.tip == 'trait definition comment'
        assert SubTraitable3.trait('trait2').ui_hint.tip == 'trait modification comment'

    def test_is_storable(self):
        self.assertFalse(SubTraitable.is_storable())
        self.assertTrue(SubTraitable2.is_storable())

        with self.assertRaisesRegex(OSError, 'No Store is available'):
            SubTraitable2().save()

        assert 'is not storable' in SubTraitable(trait1=uuid.uuid1().int).save().error()

    def test_trait_update(self):
        with CACHE_ONLY():
            instance = SubTraitable(trait1=10, trait2='hello')
            assert instance.trait2 == 'hello'

            assert instance == SubTraitable.update(trait1=10, trait2='world')
            assert instance.trait2 == 'world'

            assert instance == SubTraitable.update(trait1=10, trait2=None)  # setting to None
            assert instance.trait2 is None


class TestTraitableSlots(unittest.TestCase):
    def test_traitable_slots(self):
        expected_slots = ('T', '_default_cache', '_rev', '_collection_name')
        self.assertEqual(Traitable.__slots__, expected_slots)

    def test_subclass_slots(self):
        expected_slots = ('special_attr', *Traitable.__slots__, 'trait1', 'trait2')
        self.assertEqual(SubTraitable.__slots__, expected_slots)

    def test_instance_slots(self):
        with CACHE_ONLY():
            instance = SubTraitable(trait1=10)
        with self.assertRaises(AttributeError):
            instance.non_existent_attr = 'value'


class TestTraitable(unittest.TestCase):
    def test_init_with_id(self):
        pid = ID('John|Smith')
        p = Person(pid)
        self.assertEqual(p.id(), pid)

    def test_init_with_trait_values(self):
        with CACHE_ONLY():
            p = Person(first_name='John', last_name='Smith')
        self.assertEqual(p.first_name, 'John')
        self.assertEqual(p.last_name, 'Smith')

    def test_set_values(self):
        with CACHE_ONLY():
            p = Person(first_name='John', last_name='Smith')
        rc = p.set_values(age=19, weight_lb=200)
        self.assertTrue(rc)


class TestTraitableDynamicTraits(unittest.TestCase):
    def test_dynamic_traits(self):
        class X(Traitable):
            s_own_trait_definitions = dict(x=RT(data_type=int, get=lambda self: 10))

        x = X()
        self.assertIs(x.T.x.data_type, int)
        self.assertEqual(x.x, 10)

        class Y(X):
            y: int = RT(20)

        y = Y()
        self.assertIs(y.T.x.data_type, int)
        self.assertEqual(y.x, 10)

        self.assertIs(y.T.y.data_type, int)
        self.assertEqual(y.y, 20)
