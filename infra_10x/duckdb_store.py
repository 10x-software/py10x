from __future__ import annotations

import re
from datetime import datetime, timezone

import duckdb
import ibis

from infra_10x.ibis_store import IbisCollection, IbisStore, _ID, _REV
from core_10x.resource import Resource
from core_10x.ts_store import TsDuplicateKeyError


# ---------------------------------------------------------------------------
# DuckDbCollection — DuckDB dialect hooks
# ---------------------------------------------------------------------------


class DuckDbCollection(IbisCollection):
    def __init__(self, store: DuckDbStore, name: str):
        super().__init__(store, name)
        self._con = store._con

    def _insert_sql(self, *, overwrite: bool) -> str:
        # INSERT … RETURNING _data — single round trip (shared save_new on IbisCollection).
        verb = 'INSERT OR REPLACE' if overwrite else 'INSERT'
        return (
            f'{verb} INTO {self._qname()} ({_ID}, {_REV}, _data) VALUES (?, ?, ?) RETURNING _data'
        )

    def _handle_insert_error(self, exc: BaseException, id_val: str) -> None:
        if isinstance(exc, duckdb.ConstraintException):
            raise TsDuplicateKeyError(self._name, {_ID: id_val}) from exc
        raise exc

    def _index_expr(self, field: str) -> str | None:
        # Document schema: only real columns are indexable (no JSON expression indexes).
        if field in (_ID, _REV):
            return field
        return None


# ---------------------------------------------------------------------------
# DuckDbStore — DuckDB-specific store lifecycle
# ---------------------------------------------------------------------------


class DuckDbStore(IbisStore, resource_name='DUCK_DB'):
    """In-memory DuckDB-backed store for testing."""

    s_with_auth = False

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._con = duckdb.connect()
        self._ibis_con = ibis.duckdb.from_connection(self._con)
        self._collections: dict[str, DuckDbCollection] = {}
        self.username = kwargs.get(Resource.USERNAME_TAG, 'test_user')
        self.dbname = kwargs.get(Resource.DBNAME_TAG)

    def _execute(self, sql: str, params: list = ()) -> list[tuple]:
        return self._con.execute(sql, params).fetchall()

    @classmethod
    def standard_key(cls, *args, username=None, **kwargs) -> tuple:
        return super().standard_key(*args, **kwargs)

    @classmethod
    def new_instance(cls, *args, **kwargs) -> DuckDbStore:
        return cls(*args, **kwargs)

    def collection_names(self, regexp: str = None) -> list:
        names = sorted(self._collections.keys())
        if regexp:
            pattern = re.compile(regexp)
            names = [n for n in names if pattern.match(n)]
        return names

    def collection(self, collection_name: str) -> DuckDbCollection:
        name = collection_name
        if name not in self._collections:
            safe = name.replace('"', '""')
            self._con.execute(
                f'CREATE TABLE IF NOT EXISTS "{safe}" '
                f'({_ID} VARCHAR PRIMARY KEY, {_REV} INTEGER NOT NULL, _data VARCHAR NOT NULL)'
            )
            self._collections[name] = DuckDbCollection(self, name)
        return self._collections[name]

    def delete_collection(self, collection_name: str) -> bool:
        if collection_name not in self._collections:
            return False
        safe = collection_name.replace('"', '""')
        self._con.execute(f'DROP TABLE IF EXISTS "{safe}"')
        del self._collections[collection_name]
        return True

    @classmethod
    def is_running_with_auth(cls, host_name: str, port: int = None) -> tuple:
        return True, cls.s_with_auth

    def auth_user(self) -> str | None:
        return self.username

    def db_name(self) -> str | None:
        return self.dbname

    def server_time(self) -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def add_who(self, field: str, serialized_data: dict) -> dict:
        if field in serialized_data:
            raise RuntimeError(f'Field {field} is already in use.')
        serialized_data[field] = self.auth_user()
        return serialized_data

    def add_when(self, field: str, serialized_data: dict) -> dict:
        if field in serialized_data:
            raise RuntimeError(f'Field {field} is already in use.')
        serialized_data[field] = self.server_time()
        return serialized_data
