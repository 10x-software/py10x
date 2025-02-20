import unittest
from unittest.mock import MagicMock

from core_10x.nucleus import Nucleus
from core_10x.ts_store import TsStore
from core_10x.ts_union import TsUnion, TsUnionCollection
from core_10x.trait_filter import f, GT
from infra_10x.mongodb_store import MongoStore


class TestTsUnionCollection(unittest.TestCase):
    def setUp(self):
        self.mock_collection1 = MagicMock()
        self.mock_collection2 = MagicMock()
        self.union_collection = TsUnionCollection(self.mock_collection1, self.mock_collection2)

    def test_find(self, args=(f(x=GT(1)),)):
        self.mock_collection1.find.return_value = [{Nucleus.ID_TAG: 1}]
        self.mock_collection2.find.return_value = [{Nucleus.ID_TAG: 2}]
        results = list(self.union_collection.find(*args))
        self.assertEqual(results, [{Nucleus.ID_TAG: 1}, {Nucleus.ID_TAG: 2}])
        self.mock_collection1.find.assert_called_once_with(args and args[0] or None)
        self.mock_collection2.find.assert_called_once_with(args and args[0] or None)

    def test_no_args(self):
        self.test_find(args=())

    def test_find_empty(self):
        self.mock_collection1.find.return_value = []
        self.mock_collection2.find.return_value = []
        results = list(self.union_collection.find())
        self.assertEqual(results, [])

    def test_save_new(self):
        serialized_traitable = {Nucleus.ID_TAG: 1}
        self.union_collection.save_new(serialized_traitable)
        self.mock_collection1.save_new.assert_called_once_with(serialized_traitable)
        self.mock_collection2.save.assert_not_called()

    def test_save(self):
        serialized_traitable = {Nucleus.ID_TAG: 1}
        self.mock_collection1.exists.return_value = False
        self.union_collection.save(serialized_traitable)
        self.mock_collection1.save_new.assert_called_once_with(serialized_traitable)
        self.mock_collection1.save.assert_not_called()
        self.mock_collection2.save_new.assert_not_called()
        self.mock_collection2.save.assert_not_called()

        self.mock_collection1.reset_mock()
        self.mock_collection1.exists.return_value = True
        self.union_collection.save(serialized_traitable)
        self.mock_collection1.save_new.assert_not_called()
        self.mock_collection1.save.assert_called_once_with(serialized_traitable)
        self.mock_collection2.save_new.assert_not_called()
        self.mock_collection2.save.assert_not_called()

    def test_delete(self):
        id_value = '1'
        self.mock_collection1.delete.return_value = True
        self.mock_collection1.find.return_value = None
        self.mock_collection2.find.return_value = None
        result = self.union_collection.delete(id_value)
        self.assertTrue(result)
        self.mock_collection1.delete.assert_called_once_with(id_value)
        self.mock_collection2.delete.assert_not_called()

        self.mock_collection2.find.return_value = [{Nucleus.ID_TAG: id_value}]
        result = self.union_collection.delete(id_value)
        self.assertFalse(result)
        self.mock_collection2.delete.assert_not_called()

    def test_create_index(self):
        name = 'index_name'
        trait_name = 'trait_name'
        self.union_collection.create_index(name, trait_name)
        self.mock_collection1.create_index.assert_called_once_with(name, trait_name)
        self.mock_collection2.create_index.assert_not_called()

    def test_max(self):
        trait_name = 'trait_name'
        self.mock_collection1.max.return_value = {'trait_name': 1}
        self.mock_collection2.max.return_value = {'trait_name': 2}
        result = self.union_collection.max(trait_name)
        self.assertEqual(result, {'trait_name': 2})
        self.mock_collection1.max.assert_called_once_with(trait_name, None)
        self.mock_collection2.max.assert_called_once_with(trait_name, None)

    def test_max_empty(self):
        trait_name = 'trait_name'
        self.mock_collection1.max.return_value = None
        self.mock_collection2.max.return_value = None
        result = self.union_collection.max(trait_name)
        self.assertIsNone(result)

    def test_min(self):
        trait_name = 'trait_name'
        self.mock_collection1.min.return_value = {'trait_name': 1}
        self.mock_collection2.min.return_value = {'trait_name': 2}
        result = self.union_collection.min(trait_name)
        self.assertEqual(result, {'trait_name': 1})

    def test_min_empty(self):
        trait_name = 'trait_name'
        self.mock_collection1.min.return_value = None
        self.mock_collection2.min.return_value = None
        result = self.union_collection.min(trait_name)
        self.assertIsNone(result)


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
        hostname = 'localhost:localhost'
        dbname = 'dbname1:dbname2'
        username = ':'
        password = ':'
        store_class = 'MONGO_DB:MONGO_DB'

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

if __name__ == '__main__':
    unittest.main()
