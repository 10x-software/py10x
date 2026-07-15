from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import duckdb
import ibis

from core_10x.resource import Resource
from core_10x.ts_store import TsDuplicateKeyError
from infra_10x.ibis_store import (
    IbisStore,
    _DATA,
    _ID,
    _REV,
)

if TYPE_CHECKING:
    from collections.abc import Iterable


class DuckDbStore(IbisStore, resource_name='DUCK_DB'):
    """In-memory DuckDB-backed store for testing."""

    s_with_auth = False
    s_supports_add_column_if_not_exists = True

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._con = duckdb.connect()
        self._ibis_con = ibis.duckdb.from_connection(self._con)
        self.username = kwargs.get(Resource.USERNAME_TAG, 'test_user')
        self.dbname = kwargs.get(Resource.DBNAME_TAG)

    def _execute(self, sql: str, params: list = ()) -> list[tuple]:
        return self._con.execute(sql, params).fetchall()

    def _create_table_if_not_exists(self, collection_name: str) -> None:
        # _data is always present and NOT NULL; empty blob is stored as '{}'.
        self._con.execute(
            f'CREATE TABLE IF NOT EXISTS {self._qname(collection_name)} '
            f'({_ID} VARCHAR PRIMARY KEY, {_REV} INTEGER NOT NULL, {_DATA} VARCHAR NOT NULL)'
        )

    def _drop_table(self, collection_name: str) -> None:
        self._con.execute(f'DROP TABLE IF EXISTS {self._qname(collection_name)}')

    def _insert_sql(
        self,
        collection_name: str,
        *,
        overwrite: bool,
        column_names: Iterable[str],
        data_sql: str = '?',
    ) -> str:
        verb = 'INSERT OR REPLACE' if overwrite else 'INSERT'
        # Materialize once: may be a dict (keys) or other iterable.
        col_names = list(column_names)
        cols = [_ID, _REV, *col_names, _DATA]
        value_exprs = ['?', '?'] + ['?'] * len(col_names) + [data_sql]
        # Column names are Python identifiers; quote non-system cols for SQL keywords (e.g. by).
        col_sql = ', '.join(c if c in (_ID, _REV, _DATA) else f'"{c}"' for c in cols)
        values_sql = ', '.join(value_exprs)
        return (
            f'{verb} INTO {self._qname(collection_name)} ({col_sql}) '
            f'VALUES ({values_sql}) RETURNING {col_sql}'
        )

    def _handle_insert_error(self, exc: BaseException, collection_name: str, id_val: str) -> None:
        if isinstance(exc, duckdb.ConstraintException):
            raise TsDuplicateKeyError(collection_name, {_ID: id_val}) from exc
        raise exc

    def _server_time_sql_expr(self) -> str:
        # Server clock in JSON; ISO-like string for datetime_trait round-trip.
        return "strftime(CAST(current_timestamp AS TIMESTAMP), '%Y-%m-%dT%H:%M:%S.%f')"

    def _auth_user_sql_expr(self) -> str:
        # DuckDB current_user is the engine role ('duckdb'), not Resource username — bind app identity.
        return '?'

    def _auth_user_sql_params(self) -> list:
        return [self.auth_user()]

    @classmethod
    def standard_key(cls, *args, username=None, **kwargs) -> tuple:
        return super().standard_key(*args, **kwargs)

    @classmethod
    def new_instance(cls, *args, **kwargs) -> DuckDbStore:
        return cls(*args, **kwargs)

    @classmethod
    def is_running_with_auth(cls, host_name: str, port: int = None) -> tuple:
        return True, cls.s_with_auth

    def auth_user(self) -> str | None:
        return self.username

    def db_name(self) -> str | None:
        return self.dbname

    def server_time(self) -> datetime:
        return self._con.execute('SELECT CAST(current_timestamp AS TIMESTAMP)').fetchone()[0].replace(tzinfo=None)
