#!/usr/bin/env python3
"""
In-memory TestStore for testing TraitableHistory and other storage functionality.

This provides a lightweight, in-memory implementation of the TsStore interface
that can be used for unit tests without external dependencies like MongoDB.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core_10x.nucleus import Nucleus
from core_10x.ts_store import TsCollection, TsStore

if TYPE_CHECKING:
    from collections.abc import Iterable

    from core_10x.trait_filter import f


class TestCollection(TsCollection):
    """In-memory collection implementation for testing."""

    s_id_tag = '_id'

    def __init__(self, store: TestStore, collection_name: str):
        self.store = store
        self.collection_name = collection_name
        self._documents = {}  # id -> document
        self._indexes = {}  # index_name -> index_info

    def id_exists(self, id_value: str) -> bool:
        """Check if a document with the given ID exists."""
        return id_value in self._documents

    def find(self, query: f = None, _at_most: int = 0, _order: dict = None, _filter: f = None) -> Iterable:
        """Find documents matching the query."""
        documents = list(self._documents.values())

        # Apply query filter if provided
        if query:
            filtered_docs = []
            for doc in documents:
                if self._matches_query(doc, query):
                    filtered_docs.append(doc)
            documents = filtered_docs

        # Apply ordering if provided
        if _order:
            for field, direction in _order.items():
                documents.sort(key=lambda x: x.get(field, ''), reverse=(direction == -1))

        # Apply limit if specified
        if _at_most > 0:
            documents = documents[:_at_most]

        return iter(documents)

    def _matches_query(self, document: dict, query: f) -> bool:
        """Fallback simple query matching."""
        if not query:
            return True

        serialized_dict = {
            Nucleus.CLASS_TAG(): self.collection_name,
            # Nucleus.TYPE_TAG(): Nucleus.NX_RECORD_TAG(),
            # Nucleus.OBJECT_TAG(): document
            '_type': '_nx',
            '_obj': document,
        }
        # Deserialize the document into a traitable entity
        traitable = Nucleus.deserialize_dict(serialized_dict)

        # Use the filter's eval functionality
        return query.eval(traitable)

    def count(self, query: f = None) -> int:
        """Count documents matching the query."""
        return len(list(self.find(query)))

    def save_new(self, serialized_traitable: dict) -> int:
        """Save a new document."""
        # Handle MongoDB-style operations
        if '$set' in serialized_traitable:
            # This is a MongoDB-style update operation
            from datetime import datetime
            import uuid
            
            # Extract the data from $set
            data = serialized_traitable['$set'].copy()
            
            # Handle $currentDate operations
            if '$currentDate' in serialized_traitable:
                current_date_fields = serialized_traitable['$currentDate']
                for field in current_date_fields:
                    if current_date_fields[field] is True:
                        data[field] = datetime.utcnow()
            
            # Generate a new ID if not provided
            if '_id' not in data:
                data['_id'] = str(uuid.uuid4())
            
            # Store the document
            doc_id = data['_id']
            self._documents[doc_id] = data
            return 1
        else:
            # Regular save operation
            doc_id = serialized_traitable.get(self.s_id_tag)
            if not doc_id:
                return 0

            if doc_id in self._documents:
                return 0  # Document already exists

            self._documents[doc_id] = serialized_traitable.copy()
            return 1

    def save(self, serialized_traitable: dict) -> int:
        """Save or update a document."""
        undef_variable = next((k[1:] for k in serialized_traitable if k.startswith('$')), None)
        if undef_variable:
            raise RuntimeError(f'Use of undefined variable: {undef_variable}')
        doc_id = serialized_traitable.get(self.s_id_tag)
        assert doc_id

        rev_tag = Nucleus.REVISION_TAG()
        revision = serialized_traitable[rev_tag]

        existing_doc = self._documents.get(doc_id)
        existing_revision = existing_doc[rev_tag] if existing_doc else 0
        assert revision == existing_revision

        if existing_doc == serialized_traitable:
            return existing_revision

        revision += 1
        self._documents[doc_id] = serialized_traitable | {rev_tag: revision}

        return revision

    def delete(self, id_value: str) -> bool:
        """Delete a document by ID."""
        if id_value in self._documents:
            del self._documents[id_value]
            return True
        return False

    def create_index(self, name: str, trait_name: str, **index_args) -> str:
        """Create an index (in-memory implementation just stores the index info)."""
        self._indexes[name] = {'trait_name': trait_name, 'args': index_args}
        return f'index_{name}_created'

    def max(self, trait_name: str, filter: f = None) -> dict:
        """Find the document with the maximum value for the given trait."""
        documents = list(self.find(filter))
        if not documents:
            return {}

        max_doc = max(documents, key=lambda x: x.get(trait_name, ''))
        return max_doc

    def min(self, trait_name: str, filter: f = None) -> dict:
        """Find the document with the minimum value for the given trait."""
        documents = list(self.find(filter))
        if not documents:
            return {}

        min_doc = min(documents, key=lambda x: x.get(trait_name, ''))
        return min_doc


class TestStore(TsStore, resource_name='TestStore'):
    """In-memory store implementation for testing."""

    s_driver_name = 'TestStore'

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._collections = {}
        self._collection_names = set()
        # Set a default username for testing
        self.username = kwargs.get('username', 'test_user')

    @classmethod
    def new_instance(cls, *args, password: str = '', **kwargs) -> TestStore:
        """Create a new TestStore instance."""
        return cls(*args, **kwargs)

    def collection_names(self, regexp: str = None) -> list:
        """Get collection names, optionally filtered by regexp."""
        names = list(self._collection_names)

        if regexp:
            pattern = re.compile(regexp)
            names = [name for name in names if pattern.match(name)]

        return sorted(names)

    def collection(self, collection_name: str) -> TestCollection:
        """Get or create a collection."""
        if collection_name not in self._collections:
            self._collections[collection_name] = TestCollection(self, collection_name)
            self._collection_names.add(collection_name)

        return self._collections[collection_name]

    def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection."""
        if collection_name in self._collections:
            del self._collections[collection_name]
            self._collection_names.discard(collection_name)
            return True
        return False

    @classmethod
    def is_running_with_auth(cls, host_name: str) -> tuple:
        """TestStore doesn't require authentication."""
        return True, False

    def clear(self):
        """Clear all collections (useful for test cleanup)."""
        self._collections.clear()
        self._collection_names.clear()
    
    def auth_user(self) -> str:
        """Get the current authenticated user (for testing)."""
        return getattr(self, 'username', 'test_user')

    def get_document_count(self, collection_name: str) -> int:
        """Get the number of documents in a collection (for testing)."""
        if collection_name in self._collections:
            return len(self._collections[collection_name]._documents)
        return 0

    def get_documents(self, collection_name: str) -> list:
        """Get all documents in a collection (for testing)."""
        if collection_name in self._collections:
            return list(self._collections[collection_name]._documents.values())
        return []

    def auth_user(self) -> str | None:
        return self.username
