from unittest import mock
from uuid import uuid4

import pymongo.errors
import pytest

from core_10x.code_samples.person import Person
from infra_10x.mongodb_store import MongoStore

TEST_COLLECTION = uuid4().hex
TEST_COLLECTION1 = uuid4().hex
MONGO_URL = 'mongodb://localhost:27017/'
# MONGO_URL="mongodb+srv://HOST/?authMechanism=MONGODB-X509&authSource=%24external&tls=true&tlsCertificateKeyFile=/path/to/client.pem"

TEST_DB = 'test_db'


@pytest.fixture(scope="class")
def mongo_setup():
    mongo = MongoStore.instance(hostname=MONGO_URL, dbname=TEST_DB)
    patch1 = mock.patch('core_10x.package_refactoring.PackageRefactoring.find_class_id', return_value=TEST_COLLECTION)
    patch2 = mock.patch('core_10x.package_refactoring.PackageRefactoring.find_class_id', return_value=TEST_COLLECTION1)
    
    with mongo:
        with patch1:
            p = Person(first_name='John', last_name='Doe')
            p.set_values(age=30, weight_lbs=100)
            assert not p._rev
            p.save()
            assert p._rev == 1
            p.save()
            assert p._rev == 1

        with patch2:
            p1 = Person(first_name='Joe', last_name='Doe')
            p1.set_values(age=32, weight_lbs=200)
            p1.save()
            assert p1.age == 32
            assert p1._rev == 1
    
    yield mongo, p, p1
    
    # Cleanup
    for cn in [TEST_COLLECTION, TEST_COLLECTION1]:
        mongo.delete_collection(cn)
    assert not {TEST_COLLECTION, TEST_COLLECTION1}.intersection(mongo.collection_names('.*'))

def test_collection(mongo_setup):
    mongo, p, p1 = mongo_setup
    collection = mongo.collection(TEST_COLLECTION)
    assert collection is not None


def test_save(mongo_setup):
    mongo, p, p1 = mongo_setup
    collection = mongo.collection(TEST_COLLECTION)
    serialized_entity = p.serialize_object()
    _rev = collection.save(serialized_entity.copy())
    assert p._rev == _rev

    serialized_entity |= {'attr': {'nested': 'value'}}
    _rev = collection.save(serialized_entity.copy())
    serialized_entity |= dict(_rev=_rev)
    assert p._rev + 1 == _rev
    assert collection.load(p.id().value) == serialized_entity

    # test that nested dictionary replaces rather than updates
    serialized_entity |= {'attr': {'nested1': 'value1'}}
    _rev = collection.save(serialized_entity.copy())
    serialized_entity |= dict(_rev=_rev)
    assert p._rev + 2 == _rev
    # assert collection.load(_id) == serialized_entity|{'attr': {'nested': 'value', 'nested1': 'value1'}} #incorrect behavior
    assert collection.load(p.id().value) == serialized_entity

    # test that dots are not interpreted as nested fields at the top level
    serialized_entity |= {'attr.nested2': 'value2'}
    _rev = collection.save(serialized_entity.copy())
    serialized_entity |= dict(_rev=_rev)
    assert p._rev + 3 == _rev
    assert collection.load(p.id().value) == serialized_entity

    # check that we can have dictionary keys starting with $
    serialized_entity |= {'foo': {'$foo': 1}}
    # with pytest.raises(pymongo.errors.WriteError, match="Unrecognized expression '\\$foo',"): #incorrect behavior
    _rev = collection.save(serialized_entity.copy())
    serialized_entity |= dict(_rev=_rev)
    assert p._rev + 4 == _rev
    assert collection.load(p.id().value) == serialized_entity

    # check that we can *not* have top level keys starting with $ (current behavior, not ideal, but prob. ok)
    serialized_entity |= {'$foo': 1}
    with pytest.raises(pymongo.errors.WriteError, match='Use of undefined variable: foo'):
        _rev = collection.save(serialized_entity.copy())
    serialized_entity |= dict(_rev=_rev)
    assert p._rev + 4 == _rev
    del serialized_entity['$foo']
    assert collection.load(p.id().value) == serialized_entity

    # test that dots are not interpreted as nested fields at the nested level
    serialized_entity |= {'attr': {'nested.value': 1}}
    _rev = collection.save(serialized_entity.copy())
    serialized_entity |= dict(_rev=_rev)
    assert p._rev + 5 == _rev
    assert collection.load(p.id().value) == serialized_entity

    # check that we can unset fields
    del serialized_entity['attr']
    _rev = collection.save(serialized_entity.copy())
    serialized_entity |= dict(_rev=_rev)
    assert p._rev + 6 == _rev
    assert collection.load(p.id().value) == serialized_entity


def test_delete_restore(mongo_setup):
    mongo, p, p1 = mongo_setup
    collection = mongo.collection(TEST_COLLECTION)
    serialized_entity = p.serialize_object()
    id_value = serialized_entity['_id']
    assert collection.delete(id_value)
    assert collection.load(id_value) is None
    # TODO: restore is not implemented so use save_new meanwhile
    # assert collection.restore(id_value)
    collection.save_new(serialized_entity)
    assert collection.load(id_value) == serialized_entity


def test_find(mongo_setup):
    mongo, p, p1 = mongo_setup
    collection = mongo.collection(TEST_COLLECTION)
    result = collection.find()
    assert next(result) == p.serialize_object()
    assert list(result) == []


def test_load(mongo_setup):
    mongo, p, p1 = mongo_setup
    collection = mongo.collection(TEST_COLLECTION)
    id_value = p.id().value
    result = collection.load(id_value)
    assert result == p.serialize_object()


def test_delete(mongo_setup):
    mongo, p, p1 = mongo_setup
    collection = mongo.collection(TEST_COLLECTION1)
    id_value = p1.id().value
    result = collection.delete(id_value)
    assert result
    result = collection.load(id_value)
    assert result is None
