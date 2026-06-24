from __future__ import annotations

import pytest

from infra_10x.duckdb_store import DuckDbCollection, DuckDbStore
from infra_10x.ibis_store import _ID, _REV


@pytest.fixture
def store():
    s = DuckDbStore()
    s.collection('test')
    return s


@pytest.fixture
def collection(store) -> DuckDbCollection:
    return store.collection('test')


def _index_names(collection: DuckDbCollection) -> set[str]:
    rows = collection._con.execute(
        f"SELECT index_name FROM duckdb_indexes() WHERE table_name = '{collection.collection_name()}'"
    ).fetchall()
    return {r[0] for r in rows}


class TestCreateIndex:
    def test_id_column_creates_index(self, collection):
        collection.create_index('idx_id', _ID)
        assert 'idx_id' in _index_names(collection)

    def test_rev_column_creates_index(self, collection):
        collection.create_index('idx_rev', _REV)
        assert 'idx_rev' in _index_names(collection)

    def test_json_field_is_noop(self, collection):
        collection.create_index('idx_name', 'name')
        assert 'idx_name' not in _index_names(collection)

    def test_list_with_json_field_is_noop(self, collection):
        collection.create_index('idx_mixed', [(_ID, 1), ('name', -1)])
        assert 'idx_mixed' not in _index_names(collection)

    def test_list_id_rev_only_creates_index(self, collection):
        collection.create_index('idx_id_rev', [(_ID, 1), (_REV, -1)])
        assert 'idx_id_rev' in _index_names(collection)

    def test_returns_name(self, collection):
        assert collection.create_index('idx_id', _ID) == 'idx_id'
        assert collection.create_index('idx_json', 'foo') == 'idx_json'

    def test_idempotent(self, collection):
        collection.create_index('idx_rev', _REV)
        collection.create_index('idx_rev', _REV)  # IF NOT EXISTS — no error
        assert 'idx_rev' in _index_names(collection)
