from __future__ import annotations

import json
import re
from datetime import datetime, timezone, date
from typing import TYPE_CHECKING

import ibis

from core_10x.nucleus import Nucleus
from core_10x.resource import Resource
from core_10x.ts_store import TsCollection, TsDuplicateKeyError
from core_10x.ibis_store import IbisStore

if TYPE_CHECKING:
    from collections.abc import Iterable

    from core_10x.trait_filter import f as FilterExpr  # noqa: N812


_ID  = Nucleus.ID_TAG()
_REV = Nucleus.REVISION_TAG()

_DT_PREFIX    = '__dt__:'
_DATE_PREFIX  = '__date__:'
_BYTES_PREFIX = '__bytes__:'
_DT_STORED_FMT = '%Y-%m-%dT%H:%M:%S.%f'


def _json_encode(v):
    if isinstance(v, datetime):
        naive = v.replace(tzinfo=None)
        return f'{_DT_PREFIX}{naive.strftime(_DT_STORED_FMT)}'
    if isinstance(v, date):
        return f'{_DATE_PREFIX}{v.isoformat()}'
    if isinstance(v, bytes):
        import base64
        return f'{_BYTES_PREFIX}{base64.b64encode(v).decode()}'
    raise TypeError(f'Object of type {type(v).__name__} is not JSON serializable')


def _json_decode_hook(obj: dict) -> dict:
    for k, v in obj.items():
        if isinstance(v, str):
            if v.startswith(_DT_PREFIX):
                obj[k] = datetime.strptime(v[len(_DT_PREFIX):], _DT_STORED_FMT)
            elif v.startswith(_DATE_PREFIX):
                obj[k] = date.fromisoformat(v[len(_DATE_PREFIX):])
            elif v.startswith(_BYTES_PREFIX):
                import base64
                obj[k] = base64.b64decode(v[len(_BYTES_PREFIX):])
    return obj


# ---------------------------------------------------------------------------
# Filter → SQL helpers
# ---------------------------------------------------------------------------

def _sql_val(v) -> str:
    if v is None:
        return 'NULL'
    if isinstance(v, bool):
        return 'TRUE' if v else 'FALSE'
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, datetime):
        naive = v.replace(tzinfo=None)
        return f"STRPTIME('{naive.strftime(_DT_STORED_FMT)}', '{_DT_STORED_FMT}')"
    return "'" + str(v).replace("'", "''") + "'"


def _json_path_sql(field: str) -> str:
    if field in (_ID, _REV):
        return field
    return f"json_extract_string(_data, '$.{field}')"


def _col_for_val(field: str, rv) -> str:
    """Return appropriate SQL column expression, casting JSON string if needed for the value type."""
    col = _json_path_sql(field)
    if field in (_ID, _REV):
        return col
    if isinstance(rv, bool):
        return f'({col})::BOOLEAN'
    if isinstance(rv, int):
        return f'({col})::BIGINT'
    if isinstance(rv, float):
        return f'({col})::DOUBLE'
    if isinstance(rv, datetime):
        # Stored as __dt__:<ISO without tz> — strip prefix then parse
        return f"STRPTIME(SUBSTR({col}, {len(_DT_PREFIX) + 1}), '{_DT_STORED_FMT}')"
    return col


def _op_to_sql(field: str, op) -> str:
    from core_10x.trait_filter import (
        BETWEEN,
        EQ,
        GE,
        GT,
        IN,
        LE,
        LT,
        NE,
        NIN,
    )
    rv = op.right_value
    col = _col_for_val(field, rv)
    if isinstance(op, EQ):
        return f'{col} = {_sql_val(rv)}'
    if isinstance(op, NE):
        return f'{col} != {_sql_val(rv)}'
    if isinstance(op, GT):
        return f'{col} > {_sql_val(rv)}'
    if isinstance(op, GE):
        return f'{col} >= {_sql_val(rv)}'
    if isinstance(op, LT):
        return f'{col} < {_sql_val(rv)}'
    if isinstance(op, LE):
        return f'{col} <= {_sql_val(rv)}'
    if isinstance(op, (IN, NIN)):
        vals = ', '.join(_sql_val(v) for v in rv)
        neg = 'NOT ' if isinstance(op, NIN) else ''
        return f'{col} {neg}IN ({vals})'
    if isinstance(op, BETWEEN):
        left = _op_to_sql(field, op.left)
        right = _op_to_sql(field, op.right)
        return f'({left} AND {right})'
    raise NotImplementedError(f'Unsupported op {type(op).__name__}')


def _filter_to_sql(query: FilterExpr) -> str:
    from core_10x.trait_filter import AND, OR, f as F  # noqa: N812

    if isinstance(query, F):
        parts = []
        if query.filter:
            parts.append(_filter_to_sql(query.filter))
        for name, op in query.named_expressions.items():
            parts.append(_op_to_sql(name, op))
        return ' AND '.join(f'({p})' for p in parts) if parts else '1=1'

    if isinstance(query, AND):
        parts = [_filter_to_sql(e) for e in query.right_value]
        return '(' + ' AND '.join(parts) + ')'
    if isinstance(query, OR):
        parts = [_filter_to_sql(e) for e in query.right_value]
        return '(' + ' OR '.join(parts) + ')'

    raise NotImplementedError(f'Unsupported filter type {type(query).__name__}')


# ---------------------------------------------------------------------------
# DuckDbCollection
# ---------------------------------------------------------------------------

class DuckDbCollection(TsCollection):
    s_id_tag = _ID

    def __init__(self, store: DuckDbStore, name: str):
        self._store = store
        self._name = name
        self._con = store._con

    def collection_name(self) -> str:
        return self._name

    def _qname(self) -> str:
        return f'"{self._name}"'

    def _execute(self, sql: str, params=None):
        if params:
            return self._con.execute(sql, params)
        return self._con.execute(sql)

    def _where_clause(self, query: FilterExpr | None) -> str:
        if not query:
            return ''
        return f' WHERE {_filter_to_sql(query)}'

    def _decode_row(self, row: tuple) -> dict:
        id_val, rev, data_json = row
        doc = json.loads(data_json, object_hook=_json_decode_hook)
        doc[_ID] = id_val
        doc[_REV] = rev
        return doc

    def _encode_doc(self, doc: dict) -> tuple[str, int, str]:
        id_val = doc[_ID]
        rev = doc.get(_REV, 0)
        data = {k: v for k, v in doc.items() if k not in (_ID, _REV)}
        return id_val, rev, json.dumps(data, default=_json_encode)

    def id_exists(self, id_value: str) -> bool:
        row = self._execute(f'SELECT 1 FROM {self._qname()} WHERE {_ID} = ?', [id_value]).fetchone()
        return row is not None

    def find(self, query: FilterExpr = None, _at_most: int = 0, _order: dict = None) -> Iterable:
        sql = f'SELECT {_ID}, {_REV}, _data FROM {self._qname()}'
        sql += self._where_clause(query)
        if _order:
            order_parts = []
            for field, direction in _order.items():
                col = _json_path_sql(field)
                order_parts.append(f'{col} {"ASC" if direction >= 0 else "DESC"}')
            sql += ' ORDER BY ' + ', '.join(order_parts)
        if _at_most > 0:
            sql += f' LIMIT {_at_most}'
        rows = self._execute(sql).fetchall()
        return (self._decode_row(r) for r in rows)

    def count(self, query: FilterExpr = None) -> int:
        sql = f'SELECT COUNT(*) FROM {self._qname()}'
        sql += self._where_clause(query)
        return self._execute(sql).fetchone()[0]

    def save_new(self, serialized_traitable: dict, overwrite: bool = False) -> int:
        doc = dict(serialized_traitable)
        doc[_REV] = 1
        id_val, rev, data_json = self._encode_doc(doc)
        if not id_val:
            return 0
        try:
            if overwrite:
                self._execute(
                    f'INSERT OR REPLACE INTO {self._qname()} ({_ID}, {_REV}, _data) VALUES (?, ?, ?)',
                    [id_val, rev, data_json],
                )
            else:
                self._execute(
                    f'INSERT INTO {self._qname()} ({_ID}, {_REV}, _data) VALUES (?, ?, ?)',
                    [id_val, rev, data_json],
                )
        except Exception as e:
            if 'PRIMARY KEY' in str(e) or 'UNIQUE' in str(e) or 'duplicate' in str(e).lower():
                raise TsDuplicateKeyError(self._name, {_ID: id_val}) from e
            raise
        return 1

    def save(self, serialized_traitable: dict) -> int:
        rev = serialized_traitable[_REV]
        if rev == 0:
            return self.save_new(serialized_traitable)

        undef = next((k[1:] for k in serialized_traitable if k.startswith('$')), None)
        if undef:
            raise RuntimeError(f'Use of undefined variable: {undef}')

        doc = dict(serialized_traitable)
        id_val = doc[_ID]
        assert id_val

        new_data = {k: v for k, v in doc.items() if k not in (_ID, _REV)}
        new_data_json = json.dumps(new_data, default=_json_encode)

        # Check if data actually changed before issuing UPDATE
        row = self._execute(
            f'SELECT {_REV}, _data FROM {self._qname()} WHERE {_ID} = ?', [id_val]
        ).fetchone()
        if row:
            existing_rev, existing_data_json = row
            assert existing_rev == rev, f'Revision mismatch for {id_val}: expected {rev}, got {existing_rev}'
            if existing_data_json == new_data_json:
                return rev  # no change

        new_rev = rev + 1
        self._execute(
            f'UPDATE {self._qname()} SET {_REV} = ?, _data = ? WHERE {_ID} = ? AND {_REV} = ?',
            [new_rev, new_data_json, id_val, rev],
        )
        return new_rev

    def delete(self, id_value: str) -> bool:
        rows = self._execute(
            f'DELETE FROM {self._qname()} WHERE {_ID} = ? RETURNING {_ID}', [id_value]
        ).fetchall()
        return len(rows) > 0

    def create_index(self, name: str, trait_name: str | list[tuple[str, int]], **index_args) -> str:
        safe_name = re.sub(r'[^A-Za-z0-9_]', '_', name)
        if isinstance(trait_name, list):
            cols = ', '.join(
                f"json_extract_string(_data, '$.{tn}')" if tn not in (_ID, _REV) else tn
                for tn, _ in trait_name
            )
        elif trait_name in (_ID, _REV):
            cols = trait_name
        else:
            cols = f"json_extract_string(_data, '$.{trait_name}')"
        try:
            self._execute(f'CREATE INDEX IF NOT EXISTS {safe_name} ON {self._qname()} ({cols})')
        except Exception:
            pass  # some expressions cannot be indexed; silently skip
        return name

    def max(self, trait_name: str, filter: FilterExpr = None) -> dict:
        col = _json_path_sql(trait_name)
        where = self._where_clause(filter)
        sql = f'SELECT {_ID}, {_REV}, _data FROM {self._qname()}{where} ORDER BY {col} DESC NULLS LAST LIMIT 1'
        row = self._execute(sql).fetchone()
        return self._decode_row(row) if row else {}

    def min(self, trait_name: str, filter: FilterExpr = None) -> dict:
        col = _json_path_sql(trait_name)
        where = self._where_clause(filter)
        sql = f'SELECT {_ID}, {_REV}, _data FROM {self._qname()}{where} ORDER BY {col} ASC NULLS LAST LIMIT 1'
        row = self._execute(sql).fetchone()
        return self._decode_row(row) if row else {}


# ---------------------------------------------------------------------------
# DuckDbStore
# ---------------------------------------------------------------------------

class DuckDbStore(IbisStore, resource_name='DUCKDB_TEST_DB'):
    """In-memory DuckDB-backed store for testing."""

    s_with_auth = False

    class Transaction(IbisStore.Transaction):
        def __init__(self, store: DuckDbStore):
            self._nested = store.current_transaction() is not None
            if not self._nested:
                store._con.execute('BEGIN')
            super().__init__(store)

        def _do_commit(self) -> None:
            if not self._nested:
                self.store._con.execute('COMMIT')

        def _do_abort(self) -> None:
            if not self._nested:
                try:
                    self.store._con.execute('ROLLBACK')
                except Exception:
                    pass

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._ibis_con = ibis.duckdb.connect()
        self._con = self._ibis_con.con
        self._collections: dict[str, DuckDbCollection] = {}
        self.username = kwargs.get(Resource.USERNAME_TAG, 'test_user')
        self.dbname = kwargs.get(Resource.DBNAME_TAG)

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
                f'CREATE TABLE IF NOT EXISTS "{safe}" ({_ID} VARCHAR PRIMARY KEY, {_REV} INTEGER NOT NULL, _data VARCHAR NOT NULL)'
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
        return datetime.now(timezone.utc)
