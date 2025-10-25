"""Tests for TraitableHistory functionality using pytest and real TestStore."""

from datetime import datetime

import pytest
from core_10x.testlib.test_store import TestStore as TsStore
from core_10x.traitable import AsOfContext, T, Traitable, TraitableHistory


class NameValueTraitable(Traitable):
    """Test traitable class for testing."""

    name: str = T()
    value: int = T()


class PersonTraitable(Traitable):
    """Test person class for testing."""

    name: str = T()
    age: int = T()
    email: str = T()


@pytest.fixture
def test_store():
    """Create a test store for testing."""
    store = TsStore(username='test_user')
    store.begin_using()
    yield store
    store.end_using()


@pytest.fixture
def test_collection(test_store):
    """Create a test collection for testing."""
    return test_store.collection('test_collection')


class TestTraitableHistory:
    """Test TraitableHistory functionality."""

    def test_asof_context_enter_exit(self):
        """Test AsOfContext enter and exit."""
        as_of_time = datetime(2023, 1, 1, 12, 0, 0)

        with AsOfContext(NameValueTraitable, as_of_time) as context:
            assert context.as_of_time == as_of_time

    def test_asof_context_manager(self):
        """Test AsOfContext as context manager."""
        as_of_time = datetime(2023, 1, 1, 12, 0, 0)

        with AsOfContext(NameValueTraitable, as_of_time) as context:
            assert context.as_of_time == as_of_time

    def test_traitable_asof_method(self):
        """Test Traitable.asof method."""
        as_of_time = datetime(2023, 1, 1, 12, 0, 0)

        with NameValueTraitable.as_of(as_of_time):
            # Context should be active
            pass

    def test_traitable_history_collection(self, test_store):
        """Test TraitableHistory collection name generation."""
        # Test with default collection name
        history_coll = TraitableHistory.collection(NameValueTraitable)
        assert history_coll is not None

        # Test with custom collection name
        history_coll_custom = TraitableHistory.collection(NameValueTraitable, 'custom_collection')
        assert history_coll_custom is not None

    def test_traitable_history_save_history(self, test_store, test_collection):
        """Test the new save_history method."""
        serialized_data = {'_id': 'test-123', '_rev': 1, 'name': 'Test Item', 'value': 42}

        # Call the new save_history method
        TraitableHistory.save_history(serialized_data, test_store, test_collection, 2)

        # Verify that the history entry was saved
        assert test_collection.count() == 1

        # Get the saved document to verify its structure
        saved_docs = list(test_collection._documents.values())
        assert len(saved_docs) == 1

        saved_doc = saved_docs[0]
        assert saved_doc['_traitable_id'] == 'test-123'
        assert saved_doc['_traitable_rev'] == 2
        assert saved_doc['_who'] == 'test_user'
        assert saved_doc['name'] == 'Test Item'
        assert saved_doc['value'] == 42
        assert '_at' in saved_doc  # Should have timestamp

    def test_traitable_class_history_methods(self, test_store):
        """Test Traitable class history methods."""
        # Create a test traitable and save it with history
        test_item = NameValueTraitable()
        test_item.name = 'Test Item'
        test_item.value = 42

        # Save the traitable (this should create history)
        test_item.save()

        # Test history method
        history = NameValueTraitable.history()
        assert len(history) == 1
        assert history[0]['_traitable_id'] == test_item.id().value
        assert history[0]['_traitable_rev'] == test_item._rev
        assert history[0]['_who'] == 'test_user'
        assert '_at' in history[0]  # Should have timestamp
        assert history[0]['name'] == 'Test Item'
        assert history[0]['value'] == 42

        # Test restore method (skip for now due to test store limitations)
        # restored = TestTraitableClass.restore(test_item.id(), 1)
        # assert restored._id == test_item.id().value
        # assert restored._rev == 1
        # assert restored.name == 'Test Item'
        # assert restored.value == 42


class TestTraitableHistoryWithTestStore:
    """Test TraitableHistory functionality with real TestStore."""

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
        history_collection = test_store.collection(f'test_traitable_history/{PersonTraitable.__name__}#history')
        assert history_collection.count() == 1

        # Verify history entry structure
        history_docs = list(history_collection._documents.values())
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
        history_collection = test_store.collection(f'test_traitable_history/{PersonTraitable.__name__}#history')
        assert history_collection.count() == 2

        # Verify both history entries
        history_docs = list(history_collection._documents.values())
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
        person.save()

        # Update the person
        person.age = 31
        person.save()

        assert person._rev == 2

        # Get latest revision
        latest = PersonTraitable.latest_revision(person.id())

        # Should be the latest revision
        assert latest['_traitable_id'] == person.id().value
        assert latest['_traitable_rev'] == person._rev
        assert latest['_who'] == 'test_user'
        assert '_at' in latest
        assert latest['age'] == 31  # Updated age

    def test_asof_context_manager(self, test_store):
        """Test AsOfContext with real data."""

        # Create a person
        person = PersonTraitable()
        person.name = 'John Doe'
        person.age = 30
        person.email = 'john@example.com'
        person.save()

        # Record the time after creation
        query_time = datetime.now()

        # Update the person
        person.age = 31
        person.save()

        # Load the person as of the query time (should be the original version)
        with PersonTraitable.as_of(query_time):
            historical_person = PersonTraitable.load(person.id())
            assert historical_person.age == 30  # Original age
            assert historical_person.name == 'John Doe'

    def test_load_with_as_of(self, test_store):
        """Test loading a traitable as of a specific time."""

        # Create a person
        person = PersonTraitable()
        person.name = 'John Doe'
        person.age = 30
        person.email = 'john@example.com'
        person.save()

        # Record the time after creation
        initial_time = datetime.now()

        # Update the person
        person.age = 31
        person.save()

        # Load the person as of the initial time
        historical_person = PersonTraitable.load(person.id(), as_of=initial_time)
        assert historical_person.age == 30  # Original age
        assert historical_person.name == 'John Doe'

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
        query_time = datetime.now()

        # Update both people
        person1.age = 31
        person1.save()

        person2.age = 26
        person2.save()

        # Load all people as of the query time
        from core_10x.trait_filter import f

        historical_people = PersonTraitable.load_many(f(), as_of=query_time)

        # Should have 2 people with original ages
        assert len(historical_people) == 2

        # Find the specific people
        john = next(p for p in historical_people if p.name == 'John Doe')
        jane = next(p for p in historical_people if p.name == 'Jane Smith')

        assert john.age == 30  # Original age
        assert jane.age == 25  # Original age

    def test_history_without_s_keep_history(self, test_store):
        """Test that history is not created when s_keep_history is False."""

        # Create a class without history tracking
        class NoHistoryTraitable(Traitable):
            name: str = T()
            s_keep_history = False

        # Create and save an instance
        item = NoHistoryTraitable()
        item.name = 'Test Item'
        item.save()

        # Check that no history collection was created
        history_collection = test_store.collection(f'test_traitable_history/{NoHistoryTraitable.__name__}#history')
        assert history_collection.count() == 0

    def test_latest_revision_with_timestamp(self, test_store):
        """Test latest_revision with specific timestamp."""
        # Create a person
        person = PersonTraitable()
        person.name = 'Time Test Person'
        person.age = 30
        person.save()

        # Record time after first save
        query_time = datetime.now()

        # Update the person
        person.age = 31
        person.save()

        # Get latest revision as of the query time
        latest = TraitableHistory.latest_revision(PersonTraitable, person.id(), timestamp=query_time)

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
        from core_10x.traitable_id import ID

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
        query_time = datetime.now()
        
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

    def test_restore_with_save_parameter(self, test_store):
        """Test restore method with save parameter."""
        # Create a person
        person = PersonTraitable()
        person.name = 'Restore Test'
        person.age = 30
        person.save()
        
        # Record time after first save
        query_time = datetime.now()
        
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
        from core_10x.traitable_id import ID
        
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
        history = PersonTraitable.history()
        assert len(history) == 1
        
        history_entry = history[0]
        
        # Test deserialize
        restored_person = TraitableHistory.deserialize(PersonTraitable, person.id().collection_name, history_entry)
        
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
        history = PersonTraitable.history()
        history_entry = history[0]
        
        # Test prepare_to_deserialize
        prepared_data = TraitableHistory.prepare_to_deserialize(history_entry)
        
        # Should have the traitable data without history-specific fields
        assert prepared_data['name'] == 'Prepare Test'
        assert prepared_data['age'] == 28
        assert prepared_data['_id'] == person.id().value
        assert prepared_data['_rev'] == person._rev
        assert '_traitable_id' not in prepared_data
        assert '_traitable_rev' not in prepared_data
        assert '_who' not in prepared_data
        assert '_at' not in prepared_data


    def test_save_new_with_overwrite_parameter(self, test_store):
        """Test TestCollection.save_new with overwrite parameter."""
        # Test save_new with MongoDB-style $set operation
        collection = test_store.collection('test_collection')
        result = collection.save_new({'$set': {'_id': 'new-id', 'name': 'New Person', 'age': 25}})
        assert result == 1  # Should succeed for new document
        
        # Fails because the document already exists
        with pytest.raises(AssertionError):
            collection.save_new({'$set': {'_id': 'new-id'}})

        collection.save_new({'$set': {'_id': 'new-id'}}, overwrite=True)

    def test_find_without_filter_parameter(self, test_store):
        """Test TestCollection.find without _filter parameter."""
        # Create some test data directly in the collection
        collection = test_store.collection('test_collection')
        
        # Add documents directly to the collection
        collection._documents['doc1'] = {'name': 'Person 1', 'age': 25}
        collection._documents['doc2'] = {'name': 'Person 2', 'age': 30}
        
        # Test find without _filter parameter
        results = list(collection.find())
        assert len(results) == 2  # Should find both persons
