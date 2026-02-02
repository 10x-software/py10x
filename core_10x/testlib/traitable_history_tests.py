"""Tests for TraitableHistory functionality using pytest and real TestStore."""

from __future__ import annotations

import uuid
from datetime import date, datetime

import pytest
from core_10x_i import BTraitableProcessor
from typing_extensions import Self

from core_10x.exec_control import CACHE_ONLY, GRAPH_OFF, GRAPH_ON, INTERACTIVE
from core_10x.py_class import PyClass
from core_10x.rc import RC, RC_TRUE
from core_10x.traitable import AsOfContext, T, Traitable, TraitableHistory
from core_10x.traitable_id import ID
from core_10x.ts_store import TsDuplicateKeyError

try:
    from infra_10x.mongodb_store import MongoStore
except ImportError:
    MongoStore = None


class NameValueTraitableBase(Traitable):
    """Test traitable class for testing."""

    name: str = T()
    value: int = T()


class NameValueTraitableCustomCollection(NameValueTraitableBase):
    s_custom_collection = True


class PersonTraitableBase(Traitable):
    """Test person class for testing."""

    name: str = T()
    age: int = T()
    email: str = T()
    dob: date = T()
    spouse: Self = T()

    def spouse_set(self, trait, spouse) -> RC:
        self.raw_set_value(trait, spouse)
        if spouse:
            spouse.raw_set_value(trait, self)
        return RC_TRUE


NameValueTraitable = type(f'PersonTraitable#{uuid.uuid1().hex}', (NameValueTraitableBase,), {'__module__': __name__})
PersonTraitable = type(f'PersonTraitable#{uuid.uuid1().hex}', (PersonTraitableBase,), {'__module__': __name__})

globals()[NameValueTraitable.__name__] = NameValueTraitable
globals()[PersonTraitable.__name__] = PersonTraitable


@pytest.fixture
def test_collection(test_store):
    """Create a test collection for testing."""
    collection_name = f'test_collection_{uuid.uuid1()}'
    yield test_store.collection(collection_name=collection_name)
    test_store.delete_collection(collection_name=collection_name)
    test_store.delete_collection(collection_name=f'{collection_name}#history')


@pytest.fixture
def test_store(ts_instance):
    store = ts_instance
    store.username = 'test_user'
    store.begin_using()
    yield store
    for cls in [PersonTraitable, NameValueTraitable]:
        store.delete_collection(cls.collection().collection_name())
        store.delete_collection(cls.s_history_class.collection().collection_name())
    store.end_using()


class TestTraitableHistory:
    """Test TraitableHistory functionality."""

    def test_asof_context_enter_exit(self):
        """Test AsOfContext enter and exit."""
        as_of_time = datetime(2023, 1, 1, 12, 0, 0)

        with AsOfContext(as_of_time, [NameValueTraitable]) as context:
            assert context.as_of_time == as_of_time

    def test_asof_context_manager(self):
        """Test AsOfContext as context manager."""
        as_of_time = datetime(2023, 1, 1, 12, 0, 0)

        with AsOfContext(as_of_time, [NameValueTraitable]) as context:
            assert context.as_of_time == as_of_time

    def test_traitable_history_collection(self, test_store):
        """Test TraitableHistory collection name generation."""
        # Test with default collection name
        coll = NameValueTraitable.collection()
        history_coll = NameValueTraitable.s_history_class.collection()
        assert coll.collection_name() + '#history' == history_coll.collection_name()

    def test_traitable_history_save(self, test_store, test_collection):
        serialized_data = {'_id': 'test-123', '_rev': 1, 'name': 'Test Item', 'value': 42}

        class CustomCollectionHistory(TraitableHistory, custom_collection=True):
            s_traitable_class = Traitable

        CustomCollectionHistory(
            serialized_traitable=serialized_data,
            _traitable_rev=2,
            _collection_name=test_collection.collection_name(),
        ).save().throw()

        # Verify that the history entry was saved
        assert test_collection.count() == 1

        # Get the saved document to verify its structure
        saved_docs = list(test_collection.find())
        assert len(saved_docs) == 1

        saved_doc = saved_docs[0]
        assert saved_doc['_traitable_id'] == 'test-123'
        assert saved_doc['_traitable_rev'] == 2
        assert saved_doc['_who'] == 'test_user'
        assert saved_doc['name'] == 'Test Item'
        assert saved_doc['value'] == 42
        assert isinstance(saved_doc['_at'], datetime)

    def test_traitable_class_history_methods(self, test_store, test_collection):
        """Test Traitable class history methods."""
        # Create a test traitable and save it with history
        test_item = NameValueTraitableCustomCollection(_collection_name=test_collection.collection_name())
        test_item.name = 'Test Item'
        test_item.value = 42

        # Save the traitable (this should create history)
        test_item.save()

        assert test_item._collection_name == test_collection.collection_name()

        # Test history method
        history = NameValueTraitableCustomCollection.history(_collection_name=test_item._collection_name)
        assert len(history) == 1
        assert history[0]['_traitable_id'] == test_item.id().value
        assert history[0]['_traitable_rev'] == test_item._rev
        assert history[0]['_who'] == 'test_user'
        assert '_at' in history[0]  # Should have timestamp
        assert history[0]['name'] == 'Test Item'
        assert history[0]['value'] == 42

        ts = datetime.utcnow()
        test_item.value = 43
        test_item.save()
        assert test_item._rev == 2
        assert test_item.value == 43

        assert NameValueTraitableCustomCollection.restore(test_item.id(), ts)
        assert test_item._rev == 1
        assert test_item.value == 42

    def test_history_entry_creation(self, test_store):
        """Test that history entries are created when saving traitables."""
        # Create a person
        person = PersonTraitable()
        person.name = 'John Doe'
        person.age = 30
        person.email = 'john@example.com'

        # Save the person
        person.save()

        # Check that history was created
        history_collection = test_store.collection(f'{__name__.replace(".", "/")}/{PersonTraitable.__name__}#history')
        assert history_collection.count() == 1

        # Verify history entry structure
        history_docs = list(history_collection.find())
        history_doc = history_docs[0]
        assert history_doc['_traitable_id'] == person.id().value
        # History entry is created before revision increment, so it should be 0
        assert history_doc['_traitable_rev'] == person._rev
        assert history_doc['_who'] == 'test_user'
        assert '_at' in history_doc
        assert history_doc['name'] == 'John Doe'
        assert history_doc['age'] == 30
        assert history_doc['email'] == 'john@example.com'

    def test_multiple_history_entries(self, test_store):
        """Test that multiple history entries are created for updates."""

        # Create a person
        person = PersonTraitable()
        person.name = 'John Doe'
        person.age = 30
        person.email = 'john@example.com'
        person.save()

        # Update the person
        person.age = 31
        person.save()

        # Check that two history entries were created
        history_collection = test_store.collection(f'{__name__.replace(".", "/")}/{PersonTraitable.__name__}#history')
        assert history_collection.count() == 2

        # Verify both history entries
        history_docs = list(history_collection.find())
        assert len(history_docs) == 2

        # Both should have the same traitable_id but different revs
        traitable_ids = [doc['_traitable_id'] for doc in history_docs]
        assert all(tid == person.id().value for tid in traitable_ids)

        revs = {doc['_traitable_rev'] for doc in history_docs}
        assert {1, 2} == revs

    def test_history_method(self, test_store):
        """Test the history method."""

        # Create a person
        person = PersonTraitable()
        person.name = 'John Doe'
        person.age = 30
        person.email = 'john@example.com'
        person.save()

        # Update the person
        person.age = 31
        person.save()

        # Get history
        history = PersonTraitable.history()

        # Should have 2 history entries
        assert len(history) == 2

        # Both entries should have the correct traitable_id
        for entry in history:
            assert entry['_traitable_id'] == person.id().value
            assert entry['_who'] == 'test_user'
            assert '_at' in entry

    def test_latest_revision(self, test_store):
        """Test the latest_revision method."""

        # Create a person
        person = PersonTraitable()
        person.name = 'John Doe'
        person.age = 30
        person.email = 'john@example.com'
        person.save().throw()

        # Update the person
        person.age = 31
        person.save().throw()

        assert person._rev == 2

        # Get latest revision
        latest = PersonTraitable.latest_revision(person.id())

        # Should be the latest revision
        assert latest['_traitable_id'] == person.id().value
        assert latest['_traitable_rev'] == person._rev
        assert latest['_who'] == 'test_user'
        assert '_at' in latest
        assert latest['age'] == 31  # Updated age

    def test_asof_context_manager_ops(self, test_store):
        """Test AsOfContext with real data."""

        # Create a person
        person = PersonTraitable()
        person.name = 'John Doe'
        person.age = 30
        person.email = 'john@example.com'
        person.save()

        # Record the time after creation
        query_time = datetime.utcnow()

        # Update the person
        person.age = 31
        person.save()

        # Load the person as of the query time (should be the original version)
        with AsOfContext(query_time):
            historical_person = PersonTraitable.load(person.id())
            assert historical_person.age == 30  # Original age
            assert historical_person.name == 'John Doe'

    def test_as_of_error_cases(self, test_store):
        with BTraitableProcessor.create_root():
            # Create and save a person
            person = PersonTraitable(first_name='Alyssa', last_name='Lees', dob=date(1985, 7, 5), _replace=True)
            person.spouse = PersonTraitable(first_name='James', last_name='Bond', dob=date(1985, 7, 5), _replace=True)
            person.spouse.save().throw()
            person.save().throw()

            ts = datetime.utcnow()

            # Update and save again
            person.dob = date(1985, 7, 6)
            person.spouse.dob = date(1985, 7, 6)
            person.spouse.save().throw()
            person.save().throw()

            person_id = person.id()
            print(person.serialize_object())

            person.spouse.id()

        assert PersonTraitable.existing_instance_by_id(person_id, _throw=False)

        with CACHE_ONLY():
            assert not PersonTraitable.existing_instance_by_id(person_id, _throw=False)

        for ctx in (
            INTERACTIVE,
            GRAPH_ON,
            GRAPH_OFF,
        ):
            for as_of in (
                ts,
                None,
            ):
                with ctx():
                    person1 = PersonTraitable(person_id)
                    assert person1.dob == date(1985, 7, 6)

                    person_as_of = PersonTraitable.as_of(person_id, as_of_time=ts)

                    with AsOfContext(traitable_classes=[PersonTraitable], as_of_time=as_of):
                        with pytest.raises(RuntimeError, match=r'object not usable - origin cache is not reachable'):
                            _ = person1.dob

                        with pytest.raises(RuntimeError, match=r'object not usable - origin cache is not reachable'):
                            _ = person_as_of.dob

                        person2 = PersonTraitable(person_id)
                        assert person2.dob == (date(1985, 7, 5 + (as_of is None)))
                        assert person2.spouse.dob == (date(1985, 7, 5 + (as_of is None)))

                    assert person1.spouse.dob == date(1985, 7, 6)
                    assert person_as_of.dob == date(1985, 7, 5), person_as_of.dob

                    assert person_as_of.spouse.dob == date(1985, 7, 6)  # note - since no AsOfContext was used, nested objects are not loaded "as_of".

                    with pytest.raises(RuntimeError, match=r'object not usable - origin cache is not reachable'):
                        _ = person2.dob

    def test_load_as_of(self, test_store):
        """Test loading a traitable as of a specific time."""

        # Create a person
        person = PersonTraitable()
        person.name = 'John Doe'
        person.age = 30
        person.email = 'john@example.com'
        person.save()

        # Record the time after creation
        initial_time = datetime.utcnow()

        # Update the person
        person.age = 31
        person.save()

        # Load the person as of the initial time
        historical_person = PersonTraitable.as_of(person.id(), initial_time)
        assert historical_person.age == 30  # Original age
        assert historical_person.name == 'John Doe'
        assert historical_person == person  # person's trait values also get updated due to shared cache

    def test_load_many_with_as_of(self, test_store):
        """Test loading multiple traitables as of a specific time."""

        # Create two people
        person1 = PersonTraitable()
        person1.name = 'John Doe'
        person1.age = 30
        person1.email = 'john@example.com'
        person1.save()

        person2 = PersonTraitable()
        person2.name = 'Jane Smith'
        person2.age = 25
        person2.email = 'jane@example.com'
        person2.save()

        # Record the time after creation
        query_time = datetime.utcnow()

        # Update both people
        person1.age = 31
        person1.save()

        person2.age = 26
        person2.save()

        with AsOfContext(query_time, [PersonTraitable]):
            historical_people = PersonTraitable.load_many()

            # Should have 2 people with original ages
            assert len(historical_people) == 2

            # Find the specific people
            john = next(p for p in historical_people if p.name == 'John Doe')
            jane = next(p for p in historical_people if p.name == 'Jane Smith')

            assert john.age == 30  # Original age
            assert jane.age == 25  # Original age

        assert person1.age == 31  # Current age
        assert person2.age == 26  # Current age

    def test_history_without_keep_history(self, test_store, monkeypatch):
        """Test that history is not created when keep_history is False."""
        monkeypatch.setattr('core_10x.package_refactoring.PackageRefactoring.default_class_id', lambda cls, *args, **kwargs: PyClass.name(cls))

        # Create a class without history tracking
        class NoHistoryTraitable(Traitable, keep_history=False):
            name: str = T()

        # Create and save an instance
        item = NoHistoryTraitable()
        item.name = 'Test Item'
        item.save()

        # Check that no history collection was created
        history_collection = test_store.collection(f'{__name__.replace(".", "/")}/{NoHistoryTraitable.__name__}#history')
        assert history_collection.count() == 0

    def test_asof_with_keep_history_false_is_noop(self, test_store, monkeypatch):
        """AsOfContext with a class that has keep_history=False is a no-op: current data is used."""
        monkeypatch.setattr('core_10x.package_refactoring.PackageRefactoring.default_class_id', lambda cls, *args, **kwargs: PyClass.name(cls))

        class NoHistoryTraitable(Traitable, keep_history=False):
            key: str = T(T.ID)
            value: str = T()

        item = NoHistoryTraitable(key='k1', value='v1', _replace=True)
        item.save()
        original_helper = NoHistoryTraitable.s_storage_helper
        as_of_time = datetime(2020, 1, 1, 12, 0, 0)

        with pytest.raises(
            ValueError,
            match=r"<class 'core_10x.testlib.traitable_history_tests.TestTraitableHistory.test_asof_with_keep_history_false_is_noop.<locals>.NoHistoryTraitable'> is not storable or does not keep history",
        ):
            with AsOfContext(as_of_time, [NoHistoryTraitable]):
                pass
            assert type(NoHistoryTraitable.s_storage_helper) is type(original_helper)
        assert NoHistoryTraitable.existing_instance(key='k1') == item

    def test_asof_default_applies_to_all_traitable_subclasses(self, test_store):
        """AsOfContext with default traitable_classes (None) applies to all Traitable subclasses via __mro__."""
        # Create and save a person
        person = PersonTraitable()
        person.name = 'Default AsOf Test'
        person.age = 25
        person.save()

        query_time = datetime.utcnow()

        person.age = 26
        person.save()

        # Default: no traitable_classes => [Traitable]; PersonTraitable is a subclass so gets AsOf
        with AsOfContext(as_of_time=query_time):
            historical = PersonTraitable.load(person.id())
            assert historical is not None
            assert historical.age == 25
            assert historical.name == 'Default AsOf Test'

        # Outside context: current data
        current = PersonTraitable.load(person.id())
        assert current.age == 26

    def test_latest_revision_with_timestamp(self, test_store):
        """Test latest_revision with specific timestamp."""
        # Create a person
        person = PersonTraitable()
        person.name = 'Time Test Person'
        person.age = 30
        person.save()

        # Record time after first save
        query_time = datetime.utcnow()

        # Update the person
        person.age = 31
        person.save()

        # Get latest revision as of the query time
        latest = PersonTraitable.latest_revision(person.id(), timestamp=query_time)

        # Should be the first revision (age 30)
        assert latest['age'] == 30
        assert latest['_traitable_rev'] == 1

    def test_history_with_empty_collection(self, test_store):
        """Test history method with no history entries."""
        # Create a person but don't save it
        person = PersonTraitable()
        person.name = 'Unsaved Person'

        # Get history - should be empty
        history = PersonTraitable.history()
        assert len(history) == 0

    def test_latest_revision_with_nonexistent_id(self, test_store):
        """Test latest_revision with non-existent ID."""

        # Try to get latest revision for non-existent ID
        latest = PersonTraitable.latest_revision(ID('nonexistent'))
        assert latest is None

    def test_history_default_at_most_parameter(self, test_store):
        """Test that history method uses default _at_most=0 (no limit)."""
        # Create a person
        person = PersonTraitable()
        person.name = 'Test Person'
        person.age = 30
        person.save()

        # Update multiple times
        person.age = 31
        person.save()
        person.age = 32
        person.save()

        # Get all history entries (should get all 3)
        history = PersonTraitable.history()
        assert len(history) == 3

        # Test with explicit _at_most=2
        history_limited = PersonTraitable.history(_at_most=2)
        assert len(history_limited) == 2

    def test_latest_revision_with_timestamp_parameter(self, test_store):
        """Test that latest_revision accepts timestamp parameter."""
        # Create a person
        person = PersonTraitable()
        person.name = 'Timestamp Test'
        person.age = 25
        person.save()

        # Record time after first save
        query_time = datetime.utcnow()

        # Update the person
        person.age = 26
        person.save()

        # Test latest_revision with timestamp
        latest = PersonTraitable.latest_revision(person.id(), timestamp=query_time)
        assert latest is not None
        assert latest['age'] == 25  # Should be the first revision

        # Test latest_revision without timestamp (should get latest)
        latest_no_timestamp = PersonTraitable.latest_revision(person.id())
        assert latest_no_timestamp is not None
        assert latest_no_timestamp['age'] == 26  # Should be the latest revision

    def test_restore(self, test_store):
        """Test restore method with save parameter."""
        # Create a person
        person = PersonTraitable()
        person.name = 'Restore Test'
        person.age = 30
        person.save()

        # Record time after first save
        query_time = datetime.utcnow()

        # Update the person
        person.age = 31
        person.save()

        # Test restore without save (should not persist)
        result = PersonTraitable.restore(person.id(), timestamp=query_time, save=False)
        assert result is True
        assert person.age == 30

        # The person should still have the latest age
        person.reload()
        assert person.age == 31

        # Test restore with save (should persist)
        result = PersonTraitable.restore(person.id(), timestamp=query_time, save=True)
        assert result is True
        assert person.age == 30
        person.reload()
        assert person.age == 30

    def test_restore_with_nonexistent_timestamp(self, test_store):
        """Test restore method with non-existent timestamp."""
        # Create a person
        person = PersonTraitable()
        person.name = 'Restore Test'
        person.age = 30
        person.save()

        # Try to restore to a time before the person existed
        past_time = datetime(2020, 1, 1)
        result = PersonTraitable.restore(person.id(), timestamp=past_time, save=False)
        assert result is False

    def test_restore_with_nonexistent_id(self, test_store):
        """Test restore method with non-existent ID."""

        # Try to restore non-existent ID
        result = PersonTraitable.restore(ID('nonexistent'), save=False)
        assert result is False

    def test_traitable_history_deserialize(self, test_store):
        """Test TraitableHistory.deserialize method."""
        # Create a person
        person = PersonTraitable()
        person.name = 'Deserialize Test'
        person.age = 25
        person.save()

        # Get history entry
        history = PersonTraitable.history(_deserialize=True)
        assert len(history) == 1

        history_entry = history[0]

        # Test deserialize
        restored_person = history_entry.traitable

        assert restored_person.name == 'Deserialize Test'
        assert restored_person.age == 25
        assert restored_person.id().value == person.id().value

    def test_traitable_history_prepare_to_deserialize(self, test_store):
        """Test TraitableHistory.prepare_to_deserialize method."""
        # Create a person
        person = PersonTraitable()
        person.name = 'Prepare Test'
        person.age = 28
        person.save()

        # Get history entry
        history = PersonTraitable.history(_deserialize=True)
        history_entry = history[0]

        # Test prepare_to_deserialize
        prepared_data = history_entry.serialized_traitable

        # Should have the traitable data without history-specific fields
        assert prepared_data['name'] == 'Prepare Test'
        assert prepared_data['age'] == 28
        assert prepared_data['_id'] == person.id().value
        assert prepared_data['_rev'] == person._rev
        assert '_traitable_id' not in prepared_data
        assert '_traitable_rev' not in prepared_data
        assert '_who' not in prepared_data
        assert '_at' not in prepared_data

    def test_save_new_with_overwrite_parameter(self, test_store, test_collection):
        """Test TestCollection.save_new with overwrite parameter."""
        # Test save_new with MongoDB-style $set operation
        result = test_collection.save_new({'$set': {'_id': 'new-id', 'name': 'New Person', 'age': 25}})
        assert result == 1  # Should succeed for new document

        # Fails because the document already exists
        with pytest.raises(TsDuplicateKeyError):
            test_collection.save_new({'$set': {'_id': 'new-id'}})

        test_collection.save_new({'$set': {'_id': 'new-id'}}, overwrite=True)

    def test_find_without_filter_parameter(self, test_store, test_collection):
        """Test TestCollection.find without _filter parameter."""

        # Add documents using the interface method
        test_collection.save_new({'_id': 'doc1', 'name': 'Person 1', 'age': 25})
        test_collection.save_new({'_id': 'doc2', 'name': 'Person 2', 'age': 30})

        # Test find without _filter parameter
        results = list(test_collection.find())
        assert len(results) == 2  # Should find both persons

    def test_immutability_of_classes_without_history(self, test_store, test_collection):
        """Test immutability of storable classes that do not keep history."""

        class NoHistoryImmutableTraitable(NameValueTraitableCustomCollection, keep_history=False): ...

        # Classes without history should be marked immutable
        assert NoHistoryImmutableTraitable.s_history_class is None
        assert NoHistoryImmutableTraitable.s_immutable is True

        # First save should succeed and create a single record
        item = NoHistoryImmutableTraitable(_collection_name=test_collection.collection_name())
        item.name = 'First'
        rc1 = item.save()
        assert rc1
        assert item.name == 'First'
        assert item._rev == 1
        assert test_collection.count() == 1

        # Second save should fail (cannot update immutable records)
        item.name = 'Second'
        rc2 = item.save()
        assert not rc2
        assert item.name == 'Second'
        assert item._rev == 1

        # After reload, state should still reflect the original save
        item.reload()
        assert item.name == 'First'
        assert item._rev == 1

    def test_history_entries_are_immutable(self, test_store):
        """Test that individual history entries cannot be modified once written."""

        # Create and save a person twice to generate multiple history entries
        person = PersonTraitable()
        person.name = 'Immutable History'
        person.age = 30
        person.email = 'immutable@example.com'
        person.save()

        person.age = 31
        person.save()

        history_collection = test_store.collection(f'{__name__.replace(".", "/")}/{PersonTraitable.__name__}#history')
        assert history_collection.count() == 2

        # Load a history entry as TraitableHistory instance
        history_entries = PersonTraitable.history(_deserialize=True)
        assert len(history_entries) == 2

        entry = history_entries[0]
        original_who = entry._who

        # Attempting to modify and re-save the history entry should fail
        entry._who = 'someone-else'
        rc = entry.save()
        assert not rc

        # Reload from the store and verify that the stored entry was not changed
        reloaded_docs = list(history_collection.find())
        assert len(reloaded_docs) == 2
        assert any(doc['_who'] == original_who for doc in reloaded_docs)
        assert all(doc['_who'] != 'someone-else' for doc in reloaded_docs)

    def test_asof_find_returns_one_record_per_id(self, test_store):
        """Test that the AsOf _find implementation returns at most one record per _id."""

        # Create two people and multiple history entries for each
        person1 = PersonTraitable()
        person1.name = 'Person One'
        person1.age = 30
        person1.email = 'one@example.com'
        person1.save()

        person1.age = 31
        person1.save()

        person2 = PersonTraitable()
        person2.name = 'Person Two'
        person2.age = 25
        person2.email = 'two@example.com'
        person2.save()

        person2.age = 26
        person2.save()

        # Sanity check: we indeed have multiple history records per person
        history = PersonTraitable.history()
        assert len(history) >= 4

        as_of_time = datetime.utcnow()

        # AsOfContext uses StorableHelperAsOf._find under the hood for load_many
        with AsOfContext(as_of_time, [PersonTraitable]):
            people_as_of = PersonTraitable.load_many()

        # We should get exactly one record per traitable id
        assert len(people_as_of) == 2
        ids = [p.id().value for p in people_as_of]
        assert len(set(ids)) == len(ids)
