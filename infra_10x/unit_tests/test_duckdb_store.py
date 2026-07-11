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

    def test_unique_true(self, collection):
        """Mongo Index(..., unique=True) parity on real columns."""
        collection.create_index('idx_rev_uq', _REV, unique=True)
        assert 'idx_rev_uq' in _index_names(collection)

    def test_index_expr_none_skips_even_id(self, collection, monkeypatch):
        monkeypatch.setattr(type(collection), '_index_expr', lambda self, field: None)
        collection.create_index('idx_id', _ID)
        assert 'idx_id' not in _index_names(collection)

    def test_index_expr_override_used_for_payload_field(self, collection, monkeypatch):
        """Dialect hook maps a payload field to a real column expression."""

        def _expr(self, field: str) -> str | None:
            if field == 'name':
                return _REV  # stand-in for e.g. Postgres (_data->>'name')
            if field in (_ID, _REV):
                return field
            return None

        monkeypatch.setattr(type(collection), '_index_expr', _expr)
        collection.create_index('idx_via_hook', 'name')
        assert 'idx_via_hook' in _index_names(collection)
