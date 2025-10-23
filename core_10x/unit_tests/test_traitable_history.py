#!/usr/bin/env python3
"""
Unit tests for TraitableHistory functionality.
"""

import unittest
from datetime import datetime
from unittest.mock import Mock, patch

from core_10x.test_store import TestStore
from core_10x.traitable import AsOfContext, T, Traitable, TraitableHistory
from core_10x.traitable_id import ID


class TestTraitableClass(Traitable):
    """Test traitable class for history testing."""

    name: str = T(T.ID)
    value: int = T()


class TestTraitableHistory(unittest.TestCase):
    """Test cases for TraitableHistory functionality."""

    def test_traitable_history_collection_name(self):
        """Test history collection name generation."""
        history_name = TraitableHistory.collection_name(TestTraitableClass)
        # The collection name includes the module path
        self.assertTrue(history_name.endswith('TestTraitableClass#history'))

        # Test with custom collection name
        history_name_custom = TraitableHistory.collection_name(TestTraitableClass, 'custom_collection')
        self.assertEqual(history_name_custom, 'custom_collection#history')

    def test_traitable_history_create_entry(self):
        """Test history entry creation - now just returns a copy without _who and _at."""
        serialized_data = {'_id': 'test-123', 'name': 'Test Item', 'value': 42}

        history_entry = TraitableHistory.create_history_entry(serialized_data)

        # Should just return a copy of the original data
        # _who and _at are now computed server-side
        expected_entry = {'_id': 'test-123', 'name': 'Test Item', 'value': 42}

        self.assertEqual(history_entry, expected_entry)

    def test_traitable_history_create_entry_no_server_side_fields(self):
        """Test that create_history_entry no longer adds _who and _at fields."""
        serialized_data = {'_id': 'test-123', 'name': 'Test'}

        history_entry = TraitableHistory.create_history_entry(serialized_data)

        # Should not contain _who and _at fields (computed server-side)
        self.assertNotIn('_at', history_entry)
        self.assertNotIn('_who', history_entry)
        self.assertEqual(history_entry['_id'], 'test-123')
        self.assertEqual(history_entry['name'], 'Test')

    def test_asof_context_manager(self):
        """Test AsOfContext functionality."""
        traitable_class = TestTraitableClass
        as_of_time = datetime(2023, 1, 1, 12, 0, 0)

        context = AsOfContext(traitable_class, as_of_time)

        self.assertEqual(context.traitable_class, traitable_class)
        self.assertEqual(context.as_of_time, as_of_time)
        self.assertIsNone(context._original_as_of_time)

    def test_asof_context_enter_exit(self):
        """Test AsOfContext enter and exit behavior."""
        traitable_class = TestTraitableClass
        as_of_time = datetime(2023, 1, 1, 12, 0, 0)

        # Mock the storage helper
        mock_storage_helper = Mock()
        mock_storage_helper.as_of_time = None
        traitable_class.s_storage_helper = mock_storage_helper

        context = AsOfContext(traitable_class, as_of_time)

        # Enter context
        with context:
            # as_of_time should be set
            self.assertEqual(mock_storage_helper.as_of_time, as_of_time)

        # Exit context - as_of_time should be restored
        self.assertIsNone(mock_storage_helper.as_of_time)

    def test_traitable_asof_method(self):
        """Test Traitable.as_of method."""
        traitable_class = TestTraitableClass
        as_of_time = datetime(2023, 1, 1, 12, 0, 0)

        context = traitable_class.as_of(as_of_time)

        self.assertIsInstance(context, AsOfContext)
        self.assertEqual(context.traitable_class, traitable_class)
        self.assertEqual(context.as_of_time, as_of_time)


class TestStorableHelperHistory(unittest.TestCase):
    """Test cases for StorableHelper history functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_store = Mock()
        self.mock_collection = Mock()
        self.mock_history_collection = Mock()

        # Mock store and collections
        def mock_collection_factory(name):
            if name.endswith('_history'):
                return self.mock_history_collection
            else:
                return self.mock_collection

        self.mock_store.collection.side_effect = mock_collection_factory

        # Mock traitable class
        self.traitable_class = TestTraitableClass
        self.traitable_class.store = Mock(return_value=self.mock_store)
        self.traitable_class.s_bclass = Mock()
        self.traitable_class.s_bclass.s_id_tag = '_id'

    def test_history_collection_creation(self):
        """Test history collection creation and index setup."""
        from core_10x.traitable import StorableHelper

        # Mock the collection creation
        self.mock_history_collection.create_index.return_value = 'index_created'

        # Create StorableHelper instance
        helper = StorableHelper(self.traitable_class)
        helper.history_collection()

        # Should create the history collection (name includes module path)
        self.mock_store.collection.assert_called()
        call_args = self.mock_store.collection.call_args[0][0]
        self.assertTrue(call_args.endswith('TestTraitableClass#history'))

        # Should create indexes
        self.mock_history_collection.create_index.assert_any_call('history_id_time', [self.traitable_class.s_bclass.s_id_tag, '_at'])
        self.mock_history_collection.create_index.assert_any_call('history_time', '_at')

    def test_load_with_as_of(self):
        """Test loading with as_of parameter."""
        from core_10x.traitable import StorableHelper

        # Mock history collection and data
        mock_cursor = Mock()
        mock_cursor.__iter__ = Mock(return_value=iter([{'_id': 'test-123', 'name': 'Test', 'value': 42, '_at': datetime(2023, 1, 1, 12, 0, 0)}]))
        self.mock_history_collection.find.return_value = mock_cursor

        # Mock deserialize
        mock_traitable = Mock()
        self.traitable_class.s_bclass.deserialize_object.return_value = mock_traitable

        as_of_time = datetime(2023, 1, 1, 12, 0, 0)
        test_id = ID('test-123', 'test_collection')

        # Create StorableHelper instance
        helper = StorableHelper(self.traitable_class)
        result = helper.load(test_id, as_of_time)

        # Should query history collection
        self.mock_history_collection.find.assert_called_once()

        # Should deserialize the result
        self.traitable_class.s_bclass.deserialize_object.assert_called_once()

        self.assertEqual(result, mock_traitable)

    def test_load_many_with_as_of(self):
        """Test load_many with as_of parameter."""
        from core_10x.traitable import StorableHelper

        # Mock history collection and data
        mock_cursor = Mock()
        mock_cursor.__iter__ = Mock(
            return_value=iter(
                [
                    {'_id': 'test-123', 'name': 'Test', 'value': 42, '_at': datetime(2023, 1, 1, 12, 0, 0)},
                    {'_id': 'test-456', 'name': 'Test2', 'value': 84, '_at': datetime(2023, 1, 1, 12, 0, 0)},
                ]
            )
        )
        self.mock_history_collection.find.return_value = mock_cursor

        # Mock deserialize
        mock_traitables = [Mock(), Mock()]
        self.traitable_class.s_bclass.deserialize_object.side_effect = mock_traitables

        as_of_time = datetime(2023, 1, 1, 12, 0, 0)

        # Create StorableHelper instance
        helper = StorableHelper(self.traitable_class)
        result = helper.load_many(as_of=as_of_time)

        # Should query history collection
        self.mock_history_collection.find.assert_called_once()

        # Should deserialize results
        self.assertEqual(self.traitable_class.s_bclass.deserialize_object.call_count, 2)

        self.assertEqual(len(result), 2)

    def test_load_ids_with_as_of(self):
        """Test load_ids with as_of parameter."""
        from core_10x.traitable import StorableHelper

        # Mock history collection and data
        mock_cursor = Mock()
        mock_cursor.__iter__ = Mock(
            return_value=iter(
                [{'_id': 'test-123', '_at': datetime(2023, 1, 1, 12, 0, 0)}, {'_id': 'test-456', '_at': datetime(2023, 1, 1, 12, 0, 0)}]
            )
        )
        self.mock_history_collection.find.return_value = mock_cursor
        self.mock_history_collection.s_id_tag = '_id'

        as_of_time = datetime(2023, 1, 1, 12, 0, 0)

        # Create StorableHelper instance
        helper = StorableHelper(self.traitable_class)
        result = helper.load_ids(as_of=as_of_time)

        # Should query history collection
        self.mock_history_collection.find.assert_called_once()

        # Should return IDs
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].value, 'test-123')
        self.assertEqual(result[1].value, 'test-456')

    def test_traitable_history_methods(self):
        """Test TraitableHistory static methods."""

        # Mock history collection and data
        mock_history_data = [
            {'_id': 'test-123', 'name': 'Test', 'value': 42, '_at': datetime(2023, 1, 1, 12, 0, 0), '_who': 'user1'},
            {'_id': 'test-456', 'name': 'Test2', 'value': 84, '_at': datetime(2023, 1, 1, 11, 0, 0), '_who': 'user2'},
        ]

        # Mock the final cursor result directly
        mock_cursor = Mock()
        mock_cursor.__iter__ = Mock(return_value=iter(mock_history_data))
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.limit.return_value = iter(mock_history_data)

        self.mock_history_collection.find.return_value = mock_cursor

        # Test history method
        history_entries = TraitableHistory.history(self.traitable_class, _at_most=2)
        self.assertEqual(len(history_entries), 2)
        self.assertEqual(history_entries[0]['_id'], 'test-123')
        self.assertEqual(history_entries[0]['_who'], 'user1')

        # Test latest_revision method
        mock_cursor_latest = Mock()
        mock_cursor_latest.__iter__ = Mock(return_value=iter([mock_history_data[0]]))
        mock_cursor_latest.sort.return_value = mock_cursor_latest
        mock_cursor_latest.limit.return_value = mock_cursor_latest

        self.mock_history_collection.find.return_value = mock_cursor_latest
        latest = TraitableHistory.latest_revision(self.traitable_class, 'test-123')
        self.assertEqual(latest['_id'], 'test-123')
        self.assertEqual(latest['_who'], 'user1')

    def test_traitable_class_history_methods(self):
        """Test Traitable class history methods."""
        # Mock the TraitableHistory methods
        with (
            patch('core_10x.traitable.TraitableHistory.history') as mock_history,
            patch('core_10x.traitable.TraitableHistory.latest_revision') as mock_latest,
            patch('core_10x.traitable.TraitableHistory.restore') as mock_restore,
        ):
            mock_history.return_value = [{'_id': 'test-123', '_who': 'user1'}]
            mock_latest.return_value = {'_id': 'test-123', '_who': 'user1'}
            mock_restore.return_value = True

            # Test history method
            history = TestTraitableClass.history(_at_most=5)
            mock_history.assert_called_once_with(TestTraitableClass, 5, None)
            self.assertEqual(len(history), 1)

            # Test latest_revision method
            latest = TestTraitableClass.latest_revision('test-123')
            mock_latest.assert_called_once_with(TestTraitableClass, 'test-123')
            self.assertEqual(latest['_id'], 'test-123')

            # Test restore method
            timestamp = datetime(2023, 1, 1, 12, 0, 0)
            result = TestTraitableClass.restore('test-123', timestamp)
            mock_restore.assert_called_once_with(TestTraitableClass, 'test-123', timestamp)
            self.assertTrue(result)


class TestTraitableHistoryWithTestStore(unittest.TestCase):
    """Test TraitableHistory functionality with real TestStore."""

    def setUp(self):
        """Set up test store and traitable class."""
        self.store = TestStore()

        # Set the store as the current resource
        from core_10x.ts_store import TS_STORE

        TS_STORE.begin_using(self.store)

        # Create a test traitable class
        class TestPerson(Traitable):
            name: str = T(T.ID)
            age: int = T()
            email: str = T()

        self.TestPerson = TestPerson

    def tearDown(self):
        """Clean up after each test."""
        from core_10x.ts_store import TS_STORE

        TS_STORE.end_using()
        self.store.clear()

    def test_history_entry_creation(self):
        """Test that history entries are created on save."""
        person = self.TestPerson(name='Alice', age=25, email='alice@example.com')

        # Save the person
        rc = person.save()
        self.assertTrue(rc)

        # Check that history collection exists and has an entry
        # The collection name includes the full module path
        collection_names = self.store.collection_names()
        history_collection_name = None
        for name in collection_names:
            if name.endswith('#history'):
                history_collection_name = name
                break

        history_docs = self.store.get_documents(history_collection_name)

        self.assertEqual(len(history_docs), 1)
        history_entry = history_docs[0]

        # Check that the history entry has the required fields
        self.assertEqual(history_entry['name'], 'Alice')
        self.assertEqual(history_entry['age'], 25)
        self.assertEqual(history_entry['email'], 'alice@example.com')
        self.assertIn('_at', history_entry)
        self.assertIn('_who', history_entry)

    def test_multiple_history_entries(self):
        """Test that multiple saves create multiple history entries."""
        person = self.TestPerson(name='Bob', age=30, email='bob@example.com')

        # First save
        rc = person.save()
        self.assertTrue(rc)

        # Wait a moment and update
        import time

        time.sleep(0.1)
        person.age = 31
        person.email = 'bob.updated@example.com'

        # Second save
        rc = person.save()
        self.assertTrue(rc)

        # Check that we have 2 history entries
        # The collection name includes the full module path
        collection_names = self.store.collection_names()
        history_collection_name = None
        for name in collection_names:
            if name.endswith('#history'):
                history_collection_name = name
                break

        history_docs = self.store.get_documents(history_collection_name)

        self.assertEqual(len(history_docs), 2)

        # Check that entries have different timestamps
        timestamps = [doc['_at'] for doc in history_docs]
        self.assertNotEqual(timestamps[0], timestamps[1])

    def test_load_with_as_of(self):
        """Test loading entities as of a specific time."""
        person = self.TestPerson(name='Charlie', age=35, email='charlie@example.com')

        # Save initial version
        rc = person.save()
        self.assertTrue(rc)
        initial_time = datetime.utcnow()

        # Wait and update
        import time

        time.sleep(0.1)
        person.age = 36
        person.email = 'charlie.updated@example.com'
        rc = person.save()
        self.assertTrue(rc)

        # Load as of initial time
        historical_person = self.TestPerson.load(person.id(), as_of=initial_time)

        self.assertIsNotNone(historical_person)
        self.assertEqual(historical_person.age, 35)  # Original age
        self.assertEqual(historical_person.email, 'charlie@example.com')  # Original email

    def test_asof_context_manager(self):
        """Test the AsOf context manager."""
        person = self.TestPerson(name='David', age=40, email='david@example.com')

        # Save initial version
        rc = person.save()
        self.assertTrue(rc)
        initial_time = datetime.utcnow()

        # Wait and update
        import time

        time.sleep(0.1)
        person.age = 41
        person.email = 'david.updated@example.com'
        rc = person.save()
        self.assertTrue(rc)

        # Use AsOf context
        with self.TestPerson.as_of(initial_time):
            # Load within context should return historical version
            context_person = self.TestPerson.load(person.id())
            self.assertIsNotNone(context_person)
            self.assertEqual(context_person.age, 40)  # Original age

        # Load outside context should return current version
        current_person = self.TestPerson.load(person.id())
        self.assertIsNotNone(current_person)
        self.assertEqual(current_person.age, 41)  # Updated age

    def test_load_many_with_as_of(self):
        """Test load_many with as_of parameter."""
        # Create multiple people
        people = [
            self.TestPerson(name='Eve', age=25, email='eve@example.com'),
            self.TestPerson(name='Frank', age=30, email='frank@example.com'),
        ]

        # Save all people
        for person in people:
            rc = person.save()
            self.assertTrue(rc)

        # Record timestamp
        query_time = datetime.utcnow()

        # Update one person
        import time

        time.sleep(0.1)
        people[0].age = 26
        people[0].email = 'eve.updated@example.com'
        rc = people[0].save()
        self.assertTrue(rc)

        # Load all people as of query_time
        from core_10x.trait_filter import f

        historical_people = self.TestPerson.load_many(f(), as_of=query_time)

        self.assertEqual(len(historical_people), 2)

        # Check that we get the historical versions
        for person in historical_people:
            if person.name == 'Eve':
                self.assertEqual(person.age, 25)  # Original age
                self.assertEqual(person.email, 'eve@example.com')  # Original email
            elif person.name == 'Frank':
                self.assertEqual(person.age, 30)
                self.assertEqual(person.email, 'frank@example.com')

    def test_history_method(self):
        """Test the history() method."""
        person = self.TestPerson(name='Grace', age=45, email='grace@example.com')

        # Save multiple versions
        rc = person.save()
        self.assertTrue(rc)

        import time

        time.sleep(0.1)
        person.age = 46
        rc = person.save()
        self.assertTrue(rc)

        time.sleep(0.1)
        person.age = 47
        rc = person.save()
        self.assertTrue(rc)

        # Get history
        history_entries = self.TestPerson.history(_at_most=2)

        self.assertEqual(len(history_entries), 2)

        # Check that entries are ordered by time (most recent first)
        timestamps = [entry['_at'] for entry in history_entries]
        self.assertGreaterEqual(timestamps[0], timestamps[1])

    def test_latest_revision(self):
        """Test the latest_revision() method."""
        person = self.TestPerson(name='Henry', age=50, email='henry@example.com')

        # Save initial version
        rc = person.save()
        self.assertTrue(rc)

        # Update and save
        import time

        time.sleep(0.1)
        person.age = 51
        person.email = 'henry.updated@example.com'
        rc = person.save()
        self.assertTrue(rc)

        # Get latest revision
        latest = self.TestPerson.latest_revision(person.id())

        self.assertIsNotNone(latest)
        self.assertEqual(latest['age'], 51)  # Latest age
        self.assertEqual(latest['email'], 'henry.updated@example.com')  # Latest email


if __name__ == '__main__':
    unittest.main()
