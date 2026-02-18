#!/usr/bin/env python3
"""
In-memory TestStore for testing TraitableHistory and other storage functionality.

This provides a lightweight, in-memory implementation of the TsStore interface
that can be used for unit tests without external dependencies like MongoDB.
"""

from __future__ import annotations

import copy
from datetime import datetime
import re
from typing import TYPE_CHECKING

from py10x_kernel import BTraitable, BTraitableProcessor

from core_10x.nucleus import Nucleus
from core_10x.ts_store import TsCollection, TsDuplicateKeyError, TsStore, TsTransaction

if TYPE_CHECKING:
    from collections.abc import Iterable

    from core_10x.trait_filter import f


class TestCollection(TsCollection):
    """In-memory collection implementation for testing."""

    s_id_tag = '_id'

    def __init__(self, store: TestStore, collection_name: str):
        self.store = store
        self._collection_name = collection_name
        self._documents = {}  # id -> document
        self._indexes = {}  # index_name -> index_info

    def collection_name(self) -> str:
        return self._collection_name

    def _effective_documents(self) -> dict:
        """Documents visible in the current transaction (committed + pending, minus pending deletes)."""
        out = dict(self._documents)
        tx = self.store._current_tx
        if tx is not None:
            pending = tx.pending_saves.get(self._collection_name, {})
            deletes = tx.pending_deletes.get(self._collection_name, set())
            out.update(pending)
            for id_value in deletes:
                out.pop(id_value, None)
        return out

    def id_exists(self, id_value: str) -> bool:
        """Check if a document with the given ID exists."""
        return id_value in self._effective_documents()

    def _eval(self, doc, query):
        bclass = query.traitable_class
        try:
            return query.eval(doc)
        except AttributeError:
            # TODO: fix - need to deserialize as dictionary-based eval doesn't support nested objects
            if not bclass:
                raise  # likely and ID query from load(ID)
            coll = self._collection_name if bclass.is_custom_collection() else None
            with BTraitableProcessor.create_root():
                return query.eval(BTraitable.deserialize_object(bclass, coll, copy.copy(doc)))

    def find(self, query: f = None, _at_most: int = 0, _order: dict = None) -> Iterable:
        """Find documents matching the query."""
        documents = list(self._effective_documents().values())

        # Apply query filter if provided
        if query:
            documents = [doc for doc in documents if self._eval(doc, query)]

        # Apply ordering if provided
        if _order:
            # Sort by all fields at once, with the last field taking precedence
            # We need to reverse the order of fields so the last one is applied first
            sort_fields = list(_order.items())
            sort_fields.reverse()  # Last field first

            for field, direction in sort_fields:
                documents.sort(key=lambda x: x.get(field, ''), reverse=(direction == -1))

        # Apply limit if specified
        if _at_most > 0:
            documents = documents[:_at_most]

        return (dict(doc) for doc in documents)

    def count(self, query: f = None) -> int:
        """Count documents matching the query."""
        return len(list(self.find(query)))

    def save_new(self, serialized_traitable: dict, overwrite: bool = False) -> int:
        """Save a new document."""

        # Handle MongoDB-style operations
        if '$set' in serialized_traitable:
            # This is a MongoDB-style update operation

            # Extract the data from $set
            data = serialized_traitable['$set'].copy()

            # Handle $currentDate operations
            if '$currentDate' in serialized_traitable:
                current_date_fields = serialized_traitable['$currentDate']
                for field in current_date_fields:
                    if current_date_fields[field] is True:
                        data[field] = datetime.utcnow()

            serialized_traitable = data

        serialized_traitable[Nucleus.REVISION_TAG()] = 1

        id_tag = self.s_id_tag
        id_value = serialized_traitable.get(id_tag)

        if not id_value:
            return 0

        tx = self.store._current_tx
        if tx is not None:
            effective = self._effective_documents()
            if id_value in effective and not overwrite:
                raise TsDuplicateKeyError(self.collection_name(), {id_tag: id_value})
            if self._collection_name not in tx.pending_saves:
                tx.pending_saves[self._collection_name] = {}
            tx.pending_deletes.get(self._collection_name, set()).discard(id_value)
            tx.pending_saves[self._collection_name][id_value] = dict(serialized_traitable)
            return 1

        if id_value in self._documents and not overwrite:
            raise TsDuplicateKeyError(self.collection_name(), {id_tag: id_value})

        self._documents[id_value] = serialized_traitable
        return 1

    def save(self, serialized_traitable: dict) -> int:
        """Save or update a document."""
        rev_tag = Nucleus.REVISION_TAG()
        revision = serialized_traitable[rev_tag]
        if revision == 0:
            return self.save_new(serialized_traitable)

        undef_variable = next((k[1:] for k in serialized_traitable if k.startswith('$')), None)
        if undef_variable:
            raise RuntimeError(f'Use of undefined variable: {undef_variable}')
        doc_id = serialized_traitable.get(self.s_id_tag)
        assert doc_id

        effective = self._effective_documents()
        existing_doc = effective.get(doc_id)
        existing_revision = existing_doc[rev_tag] if existing_doc else 0
        assert revision == existing_revision

        if existing_doc == serialized_traitable:
            return existing_revision

        revision += 1
        new_doc = serialized_traitable | {rev_tag: revision}

        tx = self.store._current_tx
        if tx is not None:
            if self._collection_name not in tx.pending_saves:
                tx.pending_saves[self._collection_name] = {}
            tx.pending_deletes.get(self._collection_name, set()).discard(doc_id)
            tx.pending_saves[self._collection_name][doc_id] = new_doc
            return revision

        self._documents[doc_id] = new_doc
        return revision

    def delete(self, id_value: str) -> bool:
        """Delete a document by ID."""
        tx = self.store._current_tx
        if tx is not None:
            effective = self._effective_documents()
            if id_value not in effective:
                return False
            if self._collection_name not in tx.pending_deletes:
                tx.pending_deletes[self._collection_name] = set()
            tx.pending_deletes[self._collection_name].add(id_value)
            tx.pending_saves.get(self._collection_name, {}).pop(id_value, None)
            return True
        if id_value in self._documents:
            del self._documents[id_value]
            return True
        return False

    def create_index(self, name: str, trait_name: str | list[tuple[str, int]], **index_args) -> str:
        """Create an index (in-memory implementation just stores the index info)."""
        self._indexes[name] = {'trait_name': trait_name, 'args': index_args}
        return name

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

class TestStoreTransaction(TsTransaction):
    """In-memory transaction: commit() applies pending writes, abort() discards them."""

    def __init__(self, store: TestStore):
        super().__init__()
        self.store = store
        self.pending_saves: dict[str, dict[str, dict]] = {}  # coll_name -> id -> doc
        self.pending_deletes: dict[str, set[str]] = {}  # coll_name -> set of id
        if not store._current_tx: #TODO - nested transactions are not supported in test store
            store._current_tx = self

    def _do_commit(self) -> None:
        for coll_name, docs in self.pending_saves.items():
            if coll_name not in self.store._collections:
                continue
            coll = self.store._collections[coll_name]
            for id_value, doc in docs.items():
                coll._documents[id_value] = doc
        for coll_name, ids in self.pending_deletes.items():
            if coll_name not in self.store._collections:
                continue
            coll = self.store._collections[coll_name]
            for id_value in ids:
                coll._documents.pop(id_value, None)

    def _do_abort(self) -> None:
        pass

    def _unregister_from_store(self) -> None:
        if self.store._current_tx is self:  # TODO - nested transactions are not supported in test store
            self.store._current_tx = None


class TestStore(TsStore, resource_name='TEST_DB'):
    """In-memory store implementation for testing."""

    PROTOCOL = 'testdb'
    s_driver_name = 'TestStore'

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._collections = {}
        self._collection_names = set()
        self._current_tx = None
        # Set a default username for testing
        self.username = kwargs.get('username', 'test_user')

    @classmethod
    def new_instance(cls, *args, password: str = '', **kwargs) -> TestStore:
        """Create a new TestStore instance."""
        return cls(*args, **kwargs)

    @classmethod
    def parse_uri(cls, uri: str) -> dict:
        """Parse a test store URI (e.g. testdb: or testdb://). Returns empty kwargs."""
        if not uri.startswith('testdb:'):
            raise ValueError(f'Invalid TestStore URI: {uri}')
        return {}

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

    def _begin_transaction(self) -> TestStoreTransaction:
        return TestStoreTransaction(self)
