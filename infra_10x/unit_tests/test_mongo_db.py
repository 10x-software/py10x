import unittest

from uuid import uuid4

import pymongo.errors

from core_10x.package_refactoring import PackageRefactoring
from infra_10x.mongodb_store import MongoStore
from core_10x.code_samples.person import Person

#TEST_COLLECTION = uuid4().hex
#TEST_COLLECTION1 = uuid4().hex
TEST_COLLECTION=TEST_COLLECTION1=PackageRefactoring.find_class_id(Person)
MONGO_URL='mongodb://localhost:27017/'
#MONGO_URL="mongodb+srv://dev.qbultu3.mongodb.net/?authMechanism=MONGODB-X509&authSource=%24external&tls=true&tlsCertificateKeyFile=%2FUsers%2Fiap%2FDownloads%2FX509-cert-590074097809994161.pem"

TEST_DB='test_db'

class TestMongo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mongo = MongoStore.instance(hostname=MONGO_URL, dbname=TEST_DB, username=None, password=None)
        with cls.mongo:
            cls.p=Person(first_name='John', last_name='Doe', age=30)
            assert not cls.p._rev
            cls.p.save()
            #assert cls.p._rev == 1
            cls.p.save()
            #assert cls.p._rev == 1

            #cls.p1=Person.instance(first_name='Joe', last_name='Doe', age=32)
            #cls.p1.save(_collection_name=TEST_COLLECTION1)
            #assert cls.p1._rev == 1

    def test_collection(self):
        collection = self.mongo.collection(TEST_COLLECTION)
        self.assertIsNotNone(collection)

    def test_saveViaUpdateOne(self):
        collection = self.mongo.collection(TEST_COLLECTION)
        serialized_entity = self.p.serialize()
        _id, _rev = collection.saveViaUpdateOne(serialized_entity.copy())
        assert self.p._id() == _id
        assert self.p._rev() == _rev

        serialized_entity |= {'attr': {'nested': 'value'}}
        _id, _rev = collection.saveViaUpdateOne(serialized_entity.copy())
        serialized_entity |= dict(_rev=_rev)
        assert self.p._rev() + 1 == _rev
        assert collection.load(_id) == serialized_entity

        # test that nested dictionary replaces rather than updates
        serialized_entity |= {'attr': {'nested1': 'value1'}}
        _id, _rev = collection.saveViaUpdateOne(serialized_entity.copy())
        serialized_entity |= dict(_rev=_rev)
        assert self.p._rev() + 2 == _rev
        #assert collection.load(_id) == serialized_entity|{'attr': {'nested': 'value', 'nested1': 'value1'}} #incorrect behavior
        assert collection.load(_id) == serialized_entity

        # test that dots are not interpreted as nested fields at the top level
        serialized_entity |= {'attr.nested2': 'value2'}
        _id, _rev = collection.saveViaUpdateOne(serialized_entity.copy())
        serialized_entity |= dict(_rev=_rev)
        assert self.p._rev() + 3 == _rev
        assert collection.load(_id) == serialized_entity

        # check that we can have dictionary keys starting with $
        serialized_entity |= {'foo': {'$foo': 1}}
        #with self.assertRaisesRegex(pymongo.errors.WriteError,"Unrecognized expression '\\$foo',"): #incorrect behavior
        _id, _rev = collection.saveViaUpdateOne(serialized_entity.copy())
        serialized_entity |= dict(_rev=_rev)
        assert self.p._rev() + 4 == _rev
        assert collection.load(_id) == serialized_entity

        # check that we can *not* have top level keys starting with $ (current behavior, not ideal, but prob. ok)
        serialized_entity |= {'$foo': 1}
        with self.assertRaisesRegex(pymongo.errors.WriteError,"Use of undefined variable: foo"):
            _id, _rev = collection.saveViaUpdateOne(serialized_entity.copy())
        serialized_entity |= dict(_rev=_rev)
        assert self.p._rev() + 4 == _rev
        del serialized_entity['$foo']
        assert collection.load(_id) == serialized_entity

        # test that dots are not interpreted as nested fields at the nested level
        serialized_entity |= {'attr': {'nested.value': 1}}
        _id, _rev = collection.saveViaUpdateOne(serialized_entity.copy())
        serialized_entity |= dict(_rev=_rev)
        assert self.p._rev() + 5 == _rev
        assert collection.load(_id) == serialized_entity

        # check that we can unset fields
        del serialized_entity['attr']
        _id, _rev = collection.saveViaUpdateOne(serialized_entity.copy())
        serialized_entity |= dict(_rev=_rev)
        assert self.p._rev() + 6 == _rev
        res = collection.load(_id)
        assert res == serialized_entity

    def test_restore(self):
        collection = self.mongo.collection(TEST_COLLECTION)
        serialized_entity = self.p.serialize()
        id_value = serialized_entity['_id']
        assert collection.delete(id_value)
        assert collection.load(id_value) is None
        assert collection.restore(id_value)
        assert collection.load(id_value) == serialized_entity


    def test_find(self):
        collection = self.mongo.collection(TEST_COLLECTION)
        result = collection.find()
        assert next(result) == self.p.serialize()
        assert list(result) == []

    def test_load(self):
        collection = self.mongo.collection(TEST_COLLECTION)
        id_value = self.p.id()
        result = collection.load(id_value)
        assert result == dict(_id=self.p.id(),**self.p.serialize(True))

    def test_delete(self):
        collection = self.mongo.collection(TEST_COLLECTION1)
        id_value = self.p1._id()
        result = collection._delete(id_value)
        self.assertTrue(result)
        result = collection.load(id_value)
        assert result is None

    @classmethod
    def tearDownClass(cls):
        for cn in [TEST_COLLECTION, TEST_COLLECTION1]:
            cls.mongo.delete_collection(cn)

        assert not {TEST_COLLECTION, TEST_COLLECTION1}.intersection(cls.mongo.collection_names('.*'))




if __name__ == '__main__':
    unittest.main()
