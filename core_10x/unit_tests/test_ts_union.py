import unittest
from unittest.mock import MagicMock

from core_10x.nucleus import Nucleus
from core_10x.trait_filter import GT, f
from core_10x.ts_store import TsStore
from core_10x.ts_union import TsUnion, TsUnionCollection, _OrderKey
from infra_10x.mongodb_store import MongoStore


class TestTsUnionCollection(unittest.TestCase):
    def setUp(self):
        self.collection1 = MagicMock()
        self.collection2 = MagicMock()
        self.union = TsUnionCollection(self.collection1, self.collection2)

    def test_empty(self):
        col = TsUnionCollection()
        self.assertEqual(col.collections, ())

        self.assertFalse( col.id_exists('1') )
        self.assertFalse( col.exists(f(x=GT(1))) )
        self.assertSequenceEqual( list(col.find()), [] )
        self.assertIsNone( col.max('x') )
        self.assertIsNone( col.min('x') )
        self.assertEqual( col.count(), 0 )

    def test_find(self, args=None):
        args = (f(x=GT(1)),) if args is None else args
        self.collection1.find.return_value = [{Nucleus.ID_TAG(): 2}]
        self.collection2.find.return_value = [{Nucleus.ID_TAG(): 1}]
        results = list(self.union.find(*args))
        self.assertEqual(results, [{Nucleus.ID_TAG(): 1}, {Nucleus.ID_TAG(): 2}])
        self.collection1.find.assert_called_once_with((args and args[0]) or None,_order=None,_at_most=0)
        self.collection2.find.assert_called_once_with((args and args[0]) or None,_order=None,_at_most=0)

    def test_no_args(self):
        self.test_find(args=())

    def test_find_empty(self):
        self.collection1.find.return_value = []
        self.collection2.find.return_value = []
        results = list(self.union.find())
        self.assertEqual(results, [])

    def test_save_new(self):
        serialized_traitable = {Nucleus.ID_TAG(): 1}
        self.union.save_new(serialized_traitable)
        self.collection1.save_new.assert_called_once_with(serialized_traitable)
        self.collection2.save.assert_not_called()

    def test_save(self):
        serialized_traitable = {Nucleus.ID_TAG(): 1}
        self.collection1.exists.return_value = False
        self.union.save(serialized_traitable)
        self.collection1.save_new.assert_called_once_with(serialized_traitable)
        self.collection1.save.assert_not_called()
        self.collection2.save_new.assert_not_called()
        self.collection2.save.assert_not_called()

        self.collection1.reset_mock()
        self.collection1.exists.return_value = True
        self.union.save(serialized_traitable)
        self.collection1.save_new.assert_not_called()
        self.collection1.save.assert_called_once_with(serialized_traitable)
        self.collection2.save_new.assert_not_called()
        self.collection2.save.assert_not_called()

    def test_delete(self):
        id_value = '1'
        self.collection1.delete.return_value = True
        self.collection1.count.return_value = 0
        self.collection2.count.return_value = 0
        result = self.union.delete(id_value)
        self.assertTrue(result)
        self.collection1.delete.assert_called_once_with(id_value)
        self.collection2.delete.assert_not_called()

        self.collection2.count.return_value = 1
        result = self.union.delete(id_value)
        self.assertFalse(result)
        self.collection2.delete.assert_not_called()

    def test_create_index(self):
        name = 'index_name'
        trait_name = 'trait_name'
        self.union.create_index(name, trait_name)
        self.collection1.create_index.assert_called_once_with(name, trait_name)
        self.collection2.create_index.assert_not_called()

    def test_max(self):
        trait_name = 'trait_name'
        self.collection1.max.return_value = {'trait_name': 1}
        self.collection2.max.return_value = {'trait_name': 2}
        result = self.union.max(trait_name)
        self.assertEqual(result, {'trait_name': 2})
        self.collection1.max.assert_called_once_with(trait_name, None)
        self.collection2.max.assert_called_once_with(trait_name, None)

    def test_max_empty(self):
        trait_name = 'trait_name'
        self.collection1.max.return_value = None
        self.collection2.max.return_value = None
        result = self.union.max(trait_name)
        self.assertIsNone(result)

    def test_min(self):
        trait_name = 'trait_name'
        self.collection1.min.return_value = {'trait_name': 1}
        self.collection2.min.return_value = {'trait_name': 2}
        result = self.union.min(trait_name)
        self.assertEqual(result, {'trait_name': 1})

    def test_min_empty(self):
        trait_name = 'trait_name'
        self.collection1.min.return_value = None
        self.collection2.min.return_value = None
        result = self.union.min(trait_name)
        self.assertIsNone(result)


    def test_multiple_sort_keys(self):
        data1 = [
            {'_id': '1', 'group': 'A', 'value': 30},
            {'_id': '2', 'group': 'A', 'value': 10},
            {'_id': '3', 'group': 'B', 'value': 10},
        ]
        data2 = [
            {'_id': '5', 'group': 'A', 'value': 40},
            {'_id': '6', 'group': 'B', 'value': 20},
            {'_id': '7', 'group': 'B', 'value': 20},
        ]
        self.collection1.find.return_value = data1
        self.collection2.find.return_value = data2

        # Test multiple sort keys
        results = list(self.union.find(_order={'group': 1, 'value': -1}))
        sorted_results = [
            {'_id': '5', 'group': 'A', 'value': 40},
            {'_id': '1', 'group': 'A', 'value': 30},
            {'_id': '2', 'group': 'A', 'value': 10},
            {'_id': '6', 'group': 'B', 'value': 20},
            {'_id': '7', 'group': 'B', 'value': 20},
            {'_id': '3', 'group': 'B', 'value': 10},
        ]
        assert results == sorted_results


    def test_none_handling(self):
        data2 = [
            {'_id': '2', 'value': 20},
            {'_id': '4', 'value': 40},
        ]
        self.collection1.find.return_value = None
        self.collection2.find.return_value = data2

        # Test handling None results
        results = list(self.union.find())
        assert len(results) == 2
        assert [r['_id'] for r in results] == ['2', '4']

        # Test all collections returning None
        self.collection2.find.return_value = None
        results = list(self.union.find())
        assert len(results) == 0

    def test_sorting(self):
        data1 = [
            {'_id': '1', 'value': 30},
            {'_id': '3', 'value': 10},
        ]
        data2 = [
            {'_id': '2', 'value': 40},
            {'_id': '4', 'value': 20},
        ]
        self.collection1.find.return_value = data1
        self.collection2.find.return_value = data2

        # Test default sorting by _id ascending
        results = list(self.union.find())
        assert len(results) == 4
        assert [r['_id'] for r in results] == ['1', '2', '3', '4']

        # Test descending sort by value with limit
        results = list(self.union.find(_order={'value': -1}, _at_most=2))
        assert [r['value'] for r in results] == [40, 30]

        # Test ascending sort by value with limit
        self.collection1.find.return_value = reversed(data1)
        self.collection2.find.return_value = reversed(data2)
        results = list(self.union.find(_order={'value': 1}, _at_most=3))
        assert len(results) == 3
        assert [r['value'] for r in results] == [10, 20, 30]

    def test_sorting_dict(self):
        data1 = [
            {'_id': '1', 'dict_field': {'a': 1, 'b': 2}},
            {'_id': '3', 'dict_field': {'a': 2, 'b': 1}},
        ]
        data2 = [
            {'_id': '2', 'dict_field': {'a': 1, 'b': 3}},
            {'_id': '4', 'dict_field': {'a': 2, 'b': 2}},
        ]
        # Test ascending sort by dict field
        self.collection1.find.return_value = data1
        self.collection2.find.return_value = data2
        results = list(self.union.find(_order={'dict_field': 1}))
        assert len(results) == 4
        assert [r['_id'] for r in results] == ['1', '2', '3', '4']

        # Test descending sort by dict field
        self.collection1.find.return_value = reversed(data1)
        self.collection2.find.return_value = reversed(data2)
        results = list(self.union.find(_order={'dict_field': -1}))
        assert len(results) == 4
        assert [r['_id'] for r in results] == ['3', '1', '4', '2']


class TestTsUnion(unittest.TestCase):
    def setUp(self):
        self.mock_store1 = MagicMock()
        self.mock_store2 = MagicMock()
        self.union_store = TsUnion(self.mock_store1, self.mock_store2)

    def test_collection_names(self):
        self.mock_store1.collection_names.return_value = ['collection1']
        self.mock_store2.collection_names.return_value = ['collection2']
        result = self.union_store.collection_names()
        self.assertEqual(set(result), {'collection1', 'collection2'})
        self.mock_store1.collection_names.assert_called_once()
        self.mock_store2.collection_names.assert_called_once()

    def test_collection(self):
        collection_name = 'collection_name'
        self.mock_store1.collection.return_value = MagicMock()
        self.mock_store2.collection.return_value = MagicMock()
        result = self.union_store.collection(collection_name)
        self.assertIsInstance(result, TsUnionCollection)
        self.mock_store1.collection.assert_called_once_with(collection_name)
        self.mock_store2.collection.assert_called_once_with(collection_name)

    def test_delete_collection(self):
        collection_name = 'collection_name'
        self.union_store.delete_collection(collection_name)
        self.mock_store1.delete_collection.assert_called_once_with(collection_name)
        self.mock_store2.delete_collection.assert_not_called()

    def test_new_instance(self):
        store_spec = dict(driver_name='MONGO_DB', hostname='localhost', dbname='dbname1', username='')

        union_store = TsUnion.instance(store_spec, store_spec|dict(dbname='dbname2'))
        assert isinstance(union_store, TsUnion)
        assert all(isinstance(store, MongoStore) for store in union_store.stores)

        assert sum(1 for v in TsStore.s_instances.values() if isinstance(v, TsUnion)) == 1
        assert sum(1 for v in TsStore.s_instances.values() if isinstance(v, MongoStore)) == 2

        assert list(TsUnion.s_instances.keys()) == [
             (('dbname', 'dbname1'), ('hostname', 'localhost'), ('username', '')),
             (('dbname', 'dbname2'), ('hostname', 'localhost'), ('username', '')), (
                 (('dbname', 'dbname1'), ('driver_name', 'MONGO_DB'), ('hostname', 'localhost'), ('username', '')),
                 (('dbname', 'dbname2'), ('driver_name', 'MONGO_DB'), ('hostname', 'localhost'), ('username', ''))
            )
        ]

class TestDictLte(unittest.TestCase):
    _dict_cmp= _OrderKey._dict_cmp

    def test_equal_same_order(self):
        assert 0 == self._dict_cmp({"a": 1, "b": 2}, {"a": 1, "b": 2})

    def test_equal_different_order(self):
        assert 1 == self._dict_cmp({"b": 1, "a": 2}, {"a": 2, "b": 1})
        assert -1 == self._dict_cmp({"a": 1, "b": 2}, {"b": 2, "a": 1})

    def test_less_key_order(self):
        assert -1 == self._dict_cmp({"a": 1, "b": 2}, {"b": 2, "a": 1})  # 'a' < 'b'

    def test_greater_key_order(self):
        assert 1 == self._dict_cmp({"b": 2, "a": 1}, {"a": 1, "b": 2})  # 'b' > 'a'

    def test_less_value(self):
        assert -1 ==self._dict_cmp({"a": 1, "b": 2}, {"a": 1, "b": 3})

    def test_greater_value(self):
        assert 1 ==self._dict_cmp({"a": 1, "b": 3}, {"a": 1, "b": 2})

    def test_shorter_less(self):
        assert -1 ==self._dict_cmp({"a": 1}, {"a": 1, "b": 2})

    def test_longer_greater(self):
        assert 1 ==self._dict_cmp({"a": 1, "b": 2}, {"a": 1})

    def test_nested_less(self):
        assert -1 ==self._dict_cmp({"a": {"x": 1}}, {"a": {"y": 2}})  # 'x' < 'y'

    def test_nested_greater(self):
        assert 1 ==self._dict_cmp({"a": {"y": 2}}, {"a": {"x": 1}})  # 'y' > 'x'

    def test_example_from_query(self):
        d = {"y": 20, "x": 10}  # order: y, x
        od = {"x": 10, "y": 25}  # order: x, y
        assert 1 ==self._dict_cmp(d, od)  # 'y' > 'x'

    def test_counterexample_values_ignored_on_key_diff(self):
        d = {"a": 100}
        od = {"b": 1}
        assert -1 ==self._dict_cmp(d, od)  # 'a' < 'b', values ignored

    def test_counterexample_early_value_diff(self):
        d = {"a": 1, "c": 4}
        od = {"a": 2, "b": 3}
        assert -1 ==self._dict_cmp(d, od)  # 1 < 2, later ignored
