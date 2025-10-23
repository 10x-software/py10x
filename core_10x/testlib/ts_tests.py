from unittest import mock
from uuid import uuid4

import pytest

from core_10x.code_samples.person import Person
from core_10x.package_refactoring import PackageRefactoring
from core_10x.rc import RC_TRUE

ALIASES = [f'Person#{uuid4().hex}' for _ in range(2)]
for alias in ALIASES:
    globals()[alias] = type(alias, (Person,), {'__module__': __name__})
TEST_COLLECTION, TEST_COLLECTION1 = [PackageRefactoring.find_class_id(globals()[alias]) for alias in ALIASES]


@pytest.fixture(scope='session')
def ts_setup(ts_instance):
    patch1 = mock.patch('core_10x.package_refactoring.PackageRefactoring.find_class_id', return_value=TEST_COLLECTION)
    patch2 = mock.patch('core_10x.package_refactoring.PackageRefactoring.find_class_id', return_value=TEST_COLLECTION1)

    with ts_instance:
        with patch1:
            p = Person(first_name='John', last_name='Doe')
            p.set_values(age=30, weight_lbs=100)
            assert p._rev == 0
            assert p.save() == RC_TRUE
            assert p._rev == 1
            assert p.save() == RC_TRUE
            assert p._rev == 1

        with patch2:
            p1 = Person(first_name='Joe', last_name='Doe')
            p1.set_values(age=32, weight_lbs=200)
            assert p1.save()
            assert p1.age == 32
            assert p1._rev == 1

    yield ts_instance, p, p1

    # Cleanup
    # for cn in [TEST_COLLECTION, TEST_COLLECTION1]:
    #     ts_instance.delete_collection(cn)
    # assert not {TEST_COLLECTION, TEST_COLLECTION1}.intersection(ts_instance.collection_names('.*'))


def test_collection(ts_setup):
    ts_store, _p, _p1 = ts_setup
    collection = ts_store.collection(TEST_COLLECTION)
    assert collection is not None


def test_save(ts_setup):
    ts_store, p, _p1 = ts_setup
    collection = ts_store.collection(TEST_COLLECTION)
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
    # with pytest.raises(pyts_store.errors.WriteError, match="Unrecognized expression '\\$foo',"): #incorrect behavior
    _rev = collection.save(serialized_entity.copy())
    serialized_entity |= dict(_rev=_rev)
    assert p._rev + 4 == _rev
    assert collection.load(p.id().value) == serialized_entity

    # check that we can *not* have top level keys starting with $ (current behavior, not ideal, but prob. ok)
    serialized_entity |= {'$foo': 1}
    with pytest.raises(Exception, match='Use of undefined variable: foo'):
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


def test_delete_restore(ts_setup):
    ts_store, p, _p1 = ts_setup
    collection = ts_store.collection(TEST_COLLECTION)
    serialized_entity = p.serialize_object()
    id_value = serialized_entity['_id']
    assert collection.delete(id_value)
    assert collection.load(id_value) is None
    # TODO: restore is not implemented so use save_new meanwhile
    # assert collection.restore(id_value)
    collection.save_new(serialized_entity)
    assert collection.load(id_value) == serialized_entity


def test_find(ts_setup):
    ts_store, p, _p1 = ts_setup
    collection = ts_store.collection(TEST_COLLECTION)
    result = collection.find()
    assert next(iter(result)) == p.serialize_object()
    assert list(result) == []


def test_load(ts_setup):
    ts_store, p, _p1 = ts_setup
    collection = ts_store.collection(TEST_COLLECTION)
    id_value = p.id().value
    result = collection.load(id_value)
    assert result == p.serialize_object()


def test_delete(ts_setup):
    ts_store, _p, p1 = ts_setup
    collection = ts_store.collection(TEST_COLLECTION1)
    id_value = p1.id().value
    result = collection.delete(id_value)
    assert result
    result = collection.load(id_value)
    assert result is None
