import pytest
import polars as pl

from core_10x.rel_db import RelDb


def test_rel_db_spec_from_uri_parses_uri_components():
    spec = RelDb.spec_from_uri("pgtest://user:pass@localhost:5432/test_db")

    assert spec.resource_class is RelDb
    assert spec.kwargs[RelDb.PROTOCOL_TAG] == "pgtest"
    assert spec.kwargs[RelDb.HOSTNAME_TAG] == "localhost"
    assert spec.kwargs[RelDb.DBNAME_TAG] == "test_db"
    assert spec.kwargs[RelDb.USERNAME_TAG] == "user"
    assert spec.kwargs[RelDb.PASSWORD_TAG] == "pass"
    assert spec.kwargs[RelDb.PORT_TAG] == 5432


def test_rel_db_query_and_insert(tmp_path):
    source_df = pl.DataFrame({'a': [1, 2, 3], 'b': ['x', 'y', 'z']})

    # Use keyword-arg construction so ResourceSpec.uri() emits the four-slash form
    # (duckdb:////abs/path) that Polars ADBC requires for absolute file paths.
    db = RelDb.instance(protocol='duckdb', dbname=str(tmp_path / 'test.db'))

    with db:
        db.insert("my_table", source_df)

    # Verify in a fresh connection that the ADBC write was persisted.
    with db:
        result_df = db.query("my_table").to_polars()

    assert result_df.equals(source_df)


def test_rel_db_instance_rejects_positional_args():
    with pytest.raises(ValueError, match="keyword arguments only"):
        RelDb.instance('duckdb')


def test_rel_db_query_returns_none_for_missing_table(tmp_path):
    db = RelDb.instance(protocol='duckdb', dbname=str(tmp_path / 'test.db'))
    with db:
        result = db.query("nonexistent_table")
    assert result is None


def test_rel_db_insert_replace(tmp_path):
    db = RelDb.instance(protocol='duckdb', dbname=str(tmp_path / 'test.db'))
    original_df = pl.DataFrame({'a': [1, 2, 3], 'b': ['x', 'y', 'z']})
    replacement_df = pl.DataFrame({'a': [10, 20], 'b': ['p', 'q']})

    with db:
        db.insert("my_table", original_df)
    # DuckDB ADBC does not support if_exists='replace'; drop via ibis then re-insert.
    with db:
        db.drop_table("my_table")
    with db:
        db.insert("my_table", replacement_df)
    with db:
        result_df = db.query("my_table").to_polars()

    assert result_df.equals(replacement_df)


def test_rel_db_insert_append(tmp_path):
    db = RelDb.instance(protocol='duckdb', dbname=str(tmp_path / 'test.db'))
    first_df = pl.DataFrame({'a': [1, 2], 'b': ['x', 'y']})
    second_df = pl.DataFrame({'a': [3, 4], 'b': ['z', 'w']})

    with db:
        db.insert("my_table", first_df)
    with db:
        db.insert("my_table", second_df, if_exists='append')
    with db:
        result_df = db.query("my_table").to_polars()

    expected_df = pl.concat([first_df, second_df])
    assert result_df.equals(expected_df)


def test_rel_db_drop_table(tmp_path):
    db = RelDb.instance(protocol='duckdb', dbname=str(tmp_path / 'test.db'))
    df = pl.DataFrame({'a': [1, 2, 3]})

    # Insert via ADBC in one block, drop via ibis in the next; DuckDB requires
    # the ADBC connection to be closed before ibis can observe the committed table.
    with db:
        db.insert("my_table", df)
    with db:
        db.drop_table("my_table")
    with db:
        result = db.query("my_table")

    assert result is None


def test_rel_db_query_raises_without_context_manager(tmp_path):
    db = RelDb.instance(protocol='duckdb', dbname=str(tmp_path / 'test.db'))
    with pytest.raises(AssertionError, match="context manager"):
        db.query("my_table")


def test_rel_db_insert_raises_without_context_manager(tmp_path):
    db = RelDb.instance(protocol='duckdb', dbname=str(tmp_path / 'test.db'))
    df = pl.DataFrame({'a': [1]})
    with pytest.raises(AssertionError, match="context manager"):
        db.insert("my_table", df)


def test_rel_db_drop_table_raises_without_context_manager(tmp_path):
    db = RelDb.instance(protocol='duckdb', dbname=str(tmp_path / 'test.db'))
    with pytest.raises(AssertionError, match="context manager"):
        db.drop_table("my_table")


def test_rel_db_instance_from_uri(tmp_path):
    source_df = pl.DataFrame({'val': [42]})

    # Seed the DB via instance() — it generates the four-slash absolute-path URI
    # that the ADBC driver requires.  Then verify that instance_from_uri() can
    # round-trip the same URI and reconnect for ibis-based reads.
    db = RelDb.instance(protocol='duckdb', dbname=str(tmp_path / 'test.db'))
    with db:
        db.insert("t", source_df)

    db2 = RelDb.instance_from_uri(db._uri)
    with db2:
        result_df = db2.query("t").to_polars()

    assert result_df.equals(source_df)


def test_rel_db_connection_closed_after_context_exit(tmp_path):
    db = RelDb.instance(protocol='duckdb', dbname=str(tmp_path / 'test.db'))
    with db:
        pass
    # After exit, _connection must be cleaned up.
    assert db._connection is None
