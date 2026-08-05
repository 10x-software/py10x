"""Shared IbisStore suites against every ibis-backed dialect (DuckDB, Postgres)."""

from infra_10x.testlib.ibis_store_tests import (  # collected by pytest
    TestCreateIndex,
    collection,
    hybrid_store,
    ibis_store,
    test_datetime_filter_on_empty_table_json_path,
    test_datetime_filter_on_json_blob_casts_to_timestamp,
    test_duplicate_key_raises,
    test_hybrid_column_vs_blob_placement,
    test_index_on_scalar_column_after_save,
    test_json_field_raises,
    test_list_with_json_field_raises,
    test_schema_evolution_lazy_alter,
    test_traitable_ref_promoted_to_sql_column,
    test_ts_fields_when_eligible,
)
