from __future__ import annotations

import abc
import json
from datetime import date, datetime
from functools import reduce
from typing import TYPE_CHECKING

import ibis

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
# JSON encode / decode (used by DuckIbisCollection DML)
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
# Ibis UDF declarations — DuckDB builtins used for JSON blob queries
# ---------------------------------------------------------------------------


@ibis.udf.scalar.builtin(name='json_extract_string')
def _ibis_json_extract_string(col: str, path: str) -> str:
    """DuckDB json_extract_string — returns JSON field as a string."""
    ...


@ibis.udf.scalar.builtin(name='strptime')
def _ibis_strptime(s: str, fmt: str) -> ibis.dtype('timestamp'):
    """DuckDB strptime — parse a string into a timestamp."""
    ...


# ---------------------------------------------------------------------------
# IbisCollection — shared ibis-based query logic
# ---------------------------------------------------------------------------


class IbisCollection(TsCollection):
    """Abstract base for ibis-backed collections.

    Subclasses supply ``_ibis_table()`` (ibis table reference) and the
    DML/DDL operations (save_new, save, delete, create_index).  All
    read-path logic (find, count, max, min) lives here via ibis expressions.
    """

    s_id_tag = _ID

    @abc.abstractmethod
    def _ibis_table(self):
        """Return the ibis table expression for this collection."""
        ...

    @abc.abstractmethod
    def _qname(self) -> str: ...

    # ------------------------------------------------------------------
    # Column resolution
    # ------------------------------------------------------------------

    def _ibis_col(self, table, field: str, rv=None):
        """Return an ibis column expression for *field*, cast to match *rv*."""
        if field == _ID:
            return table._id
        if field == _REV:
            return table._rev
        col = _ibis_json_extract_string(table._data, f'$.{field}')
        if rv is None:
            return col
        if isinstance(rv, bool):
            return col.cast('boolean')
        if isinstance(rv, int):
            return col.cast('int64')
        if isinstance(rv, float):
            return col.cast('float64')
        if isinstance(rv, datetime):
            return _ibis_strptime(col[len(_DT_PREFIX) :], _DT_STORED_FMT)
        return col

    # ------------------------------------------------------------------
    # Filter → ibis expression
    # ------------------------------------------------------------------

    def _ibis_filter(self, query: FilterExpr, table):
        """Build an ibis boolean expression from *query*."""
        return query.ibis(table, self._ibis_col)

    # ------------------------------------------------------------------
    # Row decoding
    # ------------------------------------------------------------------

    def _decode_row(self, row) -> dict:
        # itertuples renames leading-underscore columns to positional _0/_1/_2
        id_val, rev, data_json = row[0], row[1], row[2]
        doc = json.loads(data_json, object_hook=_json_decode_hook)
        doc[_ID] = id_val
        doc[_REV] = rev
        return doc

    def _encode_doc(self, doc: dict) -> tuple[str, int, str]:
        id_val = doc[_ID]
        rev = doc.get(_REV, 0)
        data = {k: v for k, v in doc.items() if k not in (_ID, _REV)}
        return id_val, rev, json.dumps(data, default=_json_encode)

    # ------------------------------------------------------------------
    # Query operations
    # ------------------------------------------------------------------

    def id_exists(self, id_value: str) -> bool:
        t = self._ibis_table()
        return t.filter(t._id == id_value).count().execute() > 0

    def find(self, query: FilterExpr = None, _at_most: int = 0, _order: dict = None) -> Iterable:
        t = self._ibis_table()
        if query is not None:
            pred = self._ibis_filter(query, t)
            if pred is not None:
                t = t.filter(pred)
        if _order:
            sort_keys = []
            for field, direction in _order.items():
                col = self._ibis_col(t, field)
                sort_keys.append(col.asc() if direction >= 0 else col.desc())
            t = t.order_by(sort_keys)
        if _at_most > 0:
            t = t.limit(_at_most)
        df = t.execute()
        return (self._decode_row(row) for row in df.itertuples(index=False))

    def count(self, query: FilterExpr = None) -> int:
        t = self._ibis_table()
        if query is not None:
            pred = self._ibis_filter(query, t)
            if pred is not None:
                t = t.filter(pred)
        return t.count().execute()

    def max(self, trait_name: str, filter: FilterExpr = None) -> dict:
        t = self._ibis_table()
        if filter is not None:
            pred = self._ibis_filter(filter, t)
            if pred is not None:
                t = t.filter(pred)
        col = self._ibis_col(t, trait_name)
        df = t.order_by(col.desc()).limit(1).execute()
        if df.empty:
            return {}
        return self._decode_row(next(df.itertuples(index=False)))

    def min(self, trait_name: str, filter: FilterExpr = None) -> dict:
        t = self._ibis_table()
        if filter is not None:
            pred = self._ibis_filter(filter, t)
            if pred is not None:
                t = t.filter(pred)
        col = self._ibis_col(t, trait_name)
        df = t.order_by(col.asc()).limit(1).execute()
        if df.empty:
            return {}
        return self._decode_row(next(df.itertuples(index=False)))


# ---------------------------------------------------------------------------
# IbisStore — abstract base for ibis-backed stores
# ---------------------------------------------------------------------------


class IbisStore(TsStore):
    """Abstract base for ibis-backed stores (DuckDB, Postgres, …)."""
