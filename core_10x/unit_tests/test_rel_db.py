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
