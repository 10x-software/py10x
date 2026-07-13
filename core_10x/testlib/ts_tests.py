import time
from datetime import datetime
from typing import Any
from uuid import uuid4

import numpy
import pytest
from py10x_kernel import BTraitableProcessor, XCache

from core_10x.code_samples.person import Person as BasePerson
from core_10x.concrete_traits import datetime_trait
from core_10x.package_refactoring import PackageRefactoring
from core_10x.rc import RC_TRUE
from core_10x.trait_definition import T
from core_10x.ts_store import TsDuplicateKeyError


class EnhancedPerson(BasePerson):
    numpy_weight_lbs: Any = T()

    def numpy_weight_lbs_get(self):
        return numpy.float64(self.weight_lbs)


test_classes = {
    cls_name: type(
        cls_name,
        (EnhancedPerson,),
        {
            '__module__': __name__,
        },
        custom_collection=custom_collection
    )
    for custom_collection in (None,True)
    for cls_name in (f'Person#{uuid4().hex}{(custom_collection and "#Custom") or ""}' for _ in range(2))
}

globals().update(test_classes)


@pytest.fixture(params=[True, False], ids=['custom_collection', 'default_collection'])
def ts_setup(ts_instance,request):
    Person, Person1 = list(test_classes.values())[request.param*2:][:2] # noqa: N806
    c, c1 = [uuid4().hex if request.param else PackageRefactoring.find_class_id(cls) for cls in (Person,Person1)]

    with ts_instance:
        p = Person(first_name='John', last_name='Doe', _collection_name=c if request.param else None)
        p.set_values(age=30, weight_lbs=100)
        assert p._rev == 0
        p.save().throw()
        assert p._rev == 1
        p.save().throw()
        assert p._rev == 1
        assert p.id().collection_name == (c if request.param else None)


        p1 = Person1(first_name='Joe', last_name='Doe', _collection_name=c1 if request.param else None)
        p1.set_values(age=32, weight_lbs=200)
        p1.save().throw()
        assert p1.age == 32
        assert p1._rev == 1
        assert p1.id().collection_name == (c1 if request.param else None)

    yield ts_instance, p, p1, c, c1

    # Cleanup
    XCache.clear()
    BTraitableProcessor.current().end_using()
    for cn in [c, c1]:
        ts_instance.delete_collection(cn)
    assert not {c, c1}.intersection(ts_instance.collection_names('.*'))


class TestTSStore:
    """Test class for TS Store functionality."""

    def test_collection(self, ts_setup):
        ts_store, _p, _p1, c, _c1= ts_setup
        collection = ts_store.collection(c)
        assert collection is not None

    def test_save(self, ts_setup):
        ts_store, p, _p1, c, _c1= ts_setup

        collection = ts_store.collection(c)
        serialized_entity = p.serialize_object()
        _rev = collection.save(serialized_entity.copy())['_rev']
        assert p._rev == _rev

        serialized_entity |= {'attr': {'nested': 'value'}}
        _rev = collection.save(serialized_entity.copy())['_rev']
        serialized_entity |= dict(_rev=_rev)
        assert p._rev + 1 == _rev
        assert collection.load(p.id().value) == serialized_entity

        # test that nested dictionary replaces rather than updates
        serialized_entity |= {'attr': {'nested1': 'value1'}}
        _rev = collection.save(serialized_entity.copy())['_rev']
        serialized_entity |= dict(_rev=_rev)
        assert p._rev + 2 == _rev
        # assert collection.load(_id) == serialized_entity|{'attr': {'nested': 'value', 'nested1': 'value1'}} #incorrect behavior
        assert collection.load(p.id().value) == serialized_entity

        # test that dots are not interpreted as nested fields at the top level
        serialized_entity |= {'attr.nested2': 'value2'}
        _rev = collection.save(serialized_entity.copy())['_rev']
        serialized_entity |= dict(_rev=_rev)
        assert p._rev + 3 == _rev
        assert collection.load(p.id().value) == serialized_entity

        # Nested keys may start with $ (not operators); top-level $ is unused outside Mongo ops.
        serialized_entity |= {'foo': {'$foo': 1}}
        _rev = collection.save(serialized_entity.copy())['_rev']
        serialized_entity |= dict(_rev=_rev)
        assert p._rev + 4 == _rev
        assert collection.load(p.id().value) == serialized_entity

        # test that dots are not interpreted as nested fields at the nested level
        serialized_entity |= {'attr': {'nested.value': 1}}
        _rev = collection.save(serialized_entity.copy())['_rev']
        serialized_entity |= dict(_rev=_rev)
        assert p._rev + 5 == _rev
        assert collection.load(p.id().value) == serialized_entity

        # check that we can unset fields
        del serialized_entity['attr']
        _rev = collection.save(serialized_entity.copy())['_rev']
        serialized_entity |= dict(_rev=_rev)
        assert p._rev + 6 == _rev
        assert collection.load(p.id().value) == serialized_entity

    def test_save_with_ts_fields(self, ts_setup):
        """FOAU / RETURNING hydrate path: rev must bump on update and return store fields.

        Complements ``test_save`` (no ``_ts_fields`` → plain update / no hydrate).
        """
        ts_store, _p, _p1, c, _c1 = ts_setup
        collection = ts_store.collection(c)
        doc_id = f'ts_hydrate_{uuid4().hex}'

        r1 = collection.save_new(ts_store.add_ts('_at', T.TS_TIME, {'_id': doc_id, 'name': 'v1'}))
        assert r1['_rev'] == 1
        assert '_at' in r1

        def stamped(name: str, rev: int) -> dict:
            return ts_store.add_ts(
                '_at', T.TS_TIME, {'_id': doc_id, 'name': name, '_rev': rev}
            )

        time.sleep(0.001)
        r2 = collection.save(stamped('v2', 1))
        assert r2['_rev'] == 2, f'expected rev bump on FOAU/RETURNING update, got {r2!r}'
        assert '_at' in r2
        loaded = collection.load(doc_id)
        assert loaded['name'] == 'v2'
        assert loaded['_rev'] == 2
        assert '_at' in loaded

        time.sleep(0.001)
        r3 = collection.save(stamped('v3', 2))
        assert r3['_rev'] == 3
        assert '_at' in r3
        assert collection.load(doc_id)['name'] == 'v3'

        # Same body without prior _at literal + re-mark for stamp → still hydrates _at.
        same = collection.load(doc_id)
        body = {k: v for k, v in same.items() if k != '_at'}
        r_same = collection.save(ts_store.add_ts('_at', T.TS_TIME, body))
        assert '_at' in r_same

    def test_delete_restore(self, ts_setup):
        ts_store, p, _p1, c, _c1= ts_setup
        collection = ts_store.collection(c)
        serialized_entity = p.serialize_object()
        id_value = serialized_entity['_id']
        assert collection.delete(id_value)
        assert collection.load(id_value) is None
        # TODO: restore is not implemented so use save_new meanwhile
        # assert collection.restore(id_value)
        collection.save_new(serialized_entity)
        assert collection.load(id_value) == serialized_entity

    def test_find(self, ts_setup):
        ts_store, p, _p1, c, _c1= ts_setup
        collection = ts_store.collection(c)
        result = collection.find()
        assert next(iter(result)) == p.serialize_object()
        assert list(result) == []

    def test_load(self, ts_setup):
        ts_store, p, _p1, c, _c1= ts_setup
        collection = ts_store.collection(c)
        id_value = p.id().value
        result = collection.load(id_value)
        assert result == p.serialize_object()

    def test_delete(self, ts_setup):
        ts_store, _p, p1, _c, c1= ts_setup
        collection = ts_store.collection(c1)
        id_value = p1.id().value
        result = collection.delete(id_value)
        assert result
        result = collection.load(id_value)
        assert result is None

    def test_save_new_with_overwrite(self, ts_setup):
        """Test save_new with overwrite=True (plain and ``_ts_fields`` hydrate paths)."""
        ts_store, p, _p1, c, _c1= ts_setup
        collection = ts_store.collection(c)
        serialized_entity = p.serialize_object()
        id_value = serialized_entity['_id']

        # Plain overwrite (no hydrate)
        result = collection.save_new(serialized_entity.copy(), overwrite=True)
        assert result['_rev'] == 1
        assert collection.load(id_value) == serialized_entity
        assert list(result) == ['_rev']

        # Overwrite with store-side field hydrate
        stamped = ts_store.add_ts('_at', T.TS_TIME, {'_id': id_value, 'name': 'overwritten'})
        result = collection.save_new(stamped, overwrite=True)
        assert result['_rev'] == 1
        assert '_at' in result
        loaded = collection.load(id_value)
        assert loaded['name'] == 'overwritten'
        assert '_at' in loaded

    def test_save_new_with_ts_fields(self, ts_setup):
        """Test save_new with ``add_ts`` / server time + hydrate."""
        ts_store, _p, _p1, c, _c1= ts_setup
        collection = ts_store.collection(c)

        doc_id = 'test_doc_123'
        serialized_entity = {'_id': doc_id, 'name': 'Test Document', 'value': 42}

        dt1 = datetime.utcnow()
        time.sleep(0.001)
        result = collection.save_new(ts_store.add_ts('_at', T.TS_TIME, dict(serialized_entity)))
        time.sleep(0.001)
        dt2 = datetime.utcnow()
        assert result['_rev'] == 1
        assert set(result) == {'_rev', '_at'}

        t = datetime_trait(T())
        loaded = collection.load(doc_id)
        at = t.deserialize(loaded['_at'])
        assert isinstance(at,datetime)
        assert dt1<at<dt2, f'{dt1} < {at} < {dt2}'
        assert loaded == serialized_entity | {'_rev': 1} | {'_at': loaded['_at']}

    def test_save_new_duplicate_key_error(self, ts_setup):
        """Test that save_new raises TsDuplicateKeyError when inserting duplicate without overwrite."""
        ts_store, _p, _p1, c, _c1= ts_setup
        collection = ts_store.collection(c)

        doc_id = 'duplicate_test_123'
        result = collection.save_new({'_id': doc_id, 'name': 'Original'})
        assert result['_rev'] == 1
        loaded = collection.load(doc_id)
        assert loaded['name'] == 'Original'

        with pytest.raises(TsDuplicateKeyError, match=f'Duplicate key error collection.*dup key.*{doc_id}'):
            collection.save_new({'_id': doc_id, 'name': 'Updated'}, overwrite=False)
        loaded = collection.load(doc_id)
        assert loaded['name'] == 'Original'

        doc_id2 = 'duplicate_test_456'
        result = collection.save_new(ts_store.add_ts('_at', T.TS_TIME, {'_id': doc_id2, 'name': 'Original'}))
        assert result['_rev'] == 1
        at = result['_at']
        loaded = collection.load(doc_id2)
        assert loaded['name'] == 'Original'
        assert loaded['_at'] == at
        time.sleep(0.001)

        with pytest.raises(TsDuplicateKeyError, match=f'Duplicate key error collection.*dup key.*{doc_id2}'):
            collection.save_new(
                ts_store.add_ts('_at', T.TS_TIME, {'_id': doc_id2, 'name': 'Original'}),
                overwrite=False,
            )

        loaded = collection.load(doc_id2)
        assert loaded['name'] == 'Original'
        assert loaded['_at'] == at

    def test_save_new_with_ts_fields_and_overwrite(self, ts_setup):
        """Test save_new overwrite=True; hydrate must return refreshed store fields."""
        ts_store, _p, _p1, c, _c1= ts_setup
        collection = ts_store.collection(c)

        doc_id = 'set_overwrite_test_123'
        result = collection.save_new(ts_store.add_ts('_at', T.TS_TIME, {'_id': doc_id, 'name': 'Original'}))
        assert result['_rev'] == 1
        assert '_at' in result
        loaded = collection.load(doc_id)
        assert loaded['name'] == 'Original'
        at = loaded['_at']

        time.sleep(0.001)
        result = collection.save_new(
            ts_store.add_ts('_at', T.TS_TIME, {'_id': doc_id, 'name': 'Updated'}),
            overwrite=True,
        )
        assert result['_rev'] == 1
        assert result['_at'] > at

        loaded = collection.load(doc_id)
        assert loaded['name'] == 'Updated'
        assert loaded['_at'] > at
        assert loaded['_at'] == result['_at']

    def test_ts_class_association_ts_uri_resolution(self, ts_instance):
        """Test that TsClassAssociation.ts_uri correctly resolves store URIs for classes and their subclasses."""
        from core_10x.py_class import PyClass
        from core_10x.traitable import NamedTsStore, T, Traitable, TsClassAssociation

        class Dummy1(Traitable):
            text: str = T(T.ID)

        class Dummy2(Traitable):
            text: str = T(T.ID)

        class Dummy3(Dummy2): ...

        dummy_uri1 = 'mongodb://localhost/dummy1'
        dummy_uri2 = 'mongodb://localhost/dummy2'

        with ts_instance:
            # Create and save NamedTsStore objects
            ns1 = NamedTsStore(logical_name='dummy1', uri=dummy_uri1, _replace=True)
            ns1.save()
            ns2 = NamedTsStore(logical_name='dummy2', uri=dummy_uri2, _replace=True)
            ns2.save()

            # Create and save TsClassAssociation objects
            name1 = PyClass.name(Dummy1)
            name2 = PyClass.name(Dummy2)
            TsClassAssociation(py_canonical_name=name1, ts_logical_name='dummy1', _replace=True).save()
            TsClassAssociation(py_canonical_name=name2, ts_logical_name='dummy2', _replace=True).save()

            # Class-specific association
            assert TsClassAssociation.ts_uri(Dummy1) == dummy_uri1

            # Subclass should inherit parent's association if it has none of its own
            assert TsClassAssociation.ts_uri(Dummy3) == dummy_uri2
