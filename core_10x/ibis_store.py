from __future__ import annotations

import abc
import json
from datetime import date, datetime
from typing import TYPE_CHECKING

from core_10x.nucleus import Nucleus
from core_10x.ts_store import TsCollection, TsStore

if TYPE_CHECKING:
    from collections.abc import Iterable

    from core_10x.trait_filter import f as FilterExpr  # noqa: N812


_ID = Nucleus.ID_TAG()
_REV = Nucleus.REVISION_TAG()

_DT_PREFIX = '__dt__:'
_DATE_PREFIX = '__date__:'
_BYTES_PREFIX = '__bytes__:'
_DT_STORED_FMT = '%Y-%m-%dT%H:%M:%S.%f'


# ---------------------------------------------------------------------------
# JSON encode / decode
# ---------------------------------------------------------------------------


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
                obj[k] = datetime.strptime(v[len(_DT_PREFIX) :], _DT_STORED_FMT)
            elif v.startswith(_DATE_PREFIX):
                obj[k] = date.fromisoformat(v[len(_DATE_PREFIX) :])
            elif v.startswith(_BYTES_PREFIX):
                import base64

                obj[k] = base64.b64decode(v[len(_BYTES_PREFIX) :])
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
    """Return SQL column expression, casting the JSON string as needed for the value type."""
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
        return f"STRPTIME(SUBSTR({col}, {len(_DT_PREFIX) + 1}), '{_DT_STORED_FMT}')"
    return col


def _op_to_sql(field: str, op) -> str:
    from core_10x.trait_filter import BETWEEN, EQ, GE, GT, IN, LE, LT, NE, NIN

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
    from core_10x.trait_filter import AND, OR
    from core_10x.trait_filter import f as F  # noqa: N812

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
# IbisCollection — shared query logic for SQL/ibis-backed stores
# ---------------------------------------------------------------------------


class IbisCollection(TsCollection):
    """Abstract base for ibis-backed collections.

    Subclasses supply ``_execute()`` and the DML/DDL operations (save_new, save,
    delete, create_index).  All query logic (find, count, max, min) lives here.
    """

    s_id_tag = _ID

    @abc.abstractmethod
    def _execute(self, sql: str, params=None): ...

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
        qname = self._qname()
        row = self._execute(f'SELECT 1 FROM {qname} WHERE {_ID} = ?', [id_value]).fetchone()
        return row is not None

    def find(self, query: FilterExpr = None, _at_most: int = 0, _order: dict = None) -> Iterable:
        qname = self._qname()
        sql = f'SELECT {_ID}, {_REV}, _data FROM {qname}'
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
        qname = self._qname()
        sql = f'SELECT COUNT(*) FROM {qname}'
        sql += self._where_clause(query)
        return self._execute(sql).fetchone()[0]

    def max(self, trait_name: str, filter: FilterExpr = None) -> dict:
        qname = self._qname()
        col = _json_path_sql(trait_name)
        where = self._where_clause(filter)
        sql = f'SELECT {_ID}, {_REV}, _data FROM {qname}{where} ORDER BY {col} DESC NULLS LAST LIMIT 1'
        row = self._execute(sql).fetchone()
        return self._decode_row(row) if row else {}

    def min(self, trait_name: str, filter: FilterExpr = None) -> dict:
        qname = self._qname()
        col = _json_path_sql(trait_name)
        where = self._where_clause(filter)
        sql = f'SELECT {_ID}, {_REV}, _data FROM {qname}{where} ORDER BY {col} ASC NULLS LAST LIMIT 1'
        row = self._execute(sql).fetchone()
        return self._decode_row(row) if row else {}

    @abc.abstractmethod
    def _qname(self) -> str: ...


# ---------------------------------------------------------------------------
# IbisStore — abstract base for ibis-backed stores
# ---------------------------------------------------------------------------


class IbisStore(TsStore):
    """Abstract base for ibis-backed stores (DuckDB, Postgres, …)."""
