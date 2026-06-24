from __future__ import annotations

import abc
import json
from base64 import b64encode
from datetime import datetime
from typing import TYPE_CHECKING

import ibis
import ibis.expr.operations as ibis_ops

from core_10x.nucleus import Nucleus
from core_10x.ts_store import TsCollection, TsStore

if TYPE_CHECKING:
    from collections.abc import Iterable

    from core_10x.trait_filter import f as FilterExpr  # noqa: N812


_ID  = Nucleus.ID_TAG()
_REV = Nucleus.REVISION_TAG()


# ---------------------------------------------------------------------------
# IbisCollection — shared ibis-based query logic
# ---------------------------------------------------------------------------


class IbisCollection(TsCollection):
    """Abstract base for ibis-backed collections.

    Subclasses supply backend-specific DML/DDL (save_new, create_index).
    save(), delete(), and all read-path logic live here.
    """

    s_id_tag = _ID

    def __init__(self, store: IbisStore, name: str):
        self._store = store
        self._name = name
        self._ibis_con = store._ibis_con

    def collection_name(self) -> str:
        return self._name

    def _qname(self) -> str:
        return f'"{self._name}"'

    def _ibis_table(self):
        return self._ibis_con.table(self._name)

    def _execute(self, sql: str, params: list = ()) -> list[tuple]:
        return self._store._execute(sql, params)

    # ------------------------------------------------------------------
    # Column resolution
    # ------------------------------------------------------------------

    def _ibis_col(self, table, field: str):
        if field == _ID:
            return table._id
        if field == _REV:
            return table._rev
        return table._data.cast('json')[field]

    def ibis_col(self, name: str, trait=None):
        col = self._ibis_col(self._ibis_table(), name)
        if name in (_ID, _REV):
            return col
        if trait:
            fn = self._store.caster_map.get(trait.data_type)
            if fn:
                return fn(col)
        return ibis_ops.UnwrapJSONString(col).to_expr()

    def ibis_right_value(self, value, trait=None):
        key = trait.data_type if trait is not None else type(value)
        fn = self._store.serializer_map.get(key)
        return fn(value) if fn else value

    # ------------------------------------------------------------------
    # Filter → ibis expression
    # ------------------------------------------------------------------

    def _ibis_filter(self, query: FilterExpr):
        return query.ibis(ibis_collection=self)

    # ------------------------------------------------------------------
    # Row encoding / decoding
    # ------------------------------------------------------------------

    def _json_encode_value(self, v):
        if fn := self._store.serializer_map.get(type(v)):
            return fn(v)
        raise TypeError(f'Object of type {type(v).__name__} is not JSON serializable')

    def _decode_row(self, row) -> dict:
        id_val, rev, data_json = row
        doc = json.loads(data_json)
        doc[_ID] = id_val
        doc[_REV] = rev
        return doc

    def _encode_doc(self, doc: dict) -> tuple[str, int, str]:
        id_val = doc[_ID]
        rev = doc.get(_REV, 0)
        data = {k: v for k, v in doc.items() if k not in (_ID, _REV)}
        return id_val, rev, json.dumps(data, default=self._json_encode_value)

    # ------------------------------------------------------------------
    # DML operations
    # ------------------------------------------------------------------

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
        new_data_json = json.dumps(new_data, default=self._json_encode_value)

        rows = self._execute(
            f'SELECT {_REV}, _data FROM {self._qname()} WHERE {_ID} = ?', [id_val]
        )
        if rows:
            existing_rev, existing_data_json = rows[0]
            assert existing_rev == rev, f'Revision mismatch for {id_val}: expected {rev}, got {existing_rev}'
            if existing_data_json == new_data_json:
                return rev

        new_rev = rev + 1
        rows = self._execute(
            f'UPDATE {self._qname()} SET {_REV} = ?, _data = ? WHERE {_ID} = ? AND {_REV} = ? RETURNING {_ID}',
            [new_rev, new_data_json, id_val, rev],
        )
        if not rows:
            raise RuntimeError(f'Revision conflict saving {id_val}: rev {rev} no longer current')
        return new_rev

    def delete(self, id_value: str) -> bool:
        rows = self._execute(
            f'DELETE FROM {self._qname()} WHERE {_ID} = ? RETURNING {_ID}', [id_value]
        )
        return len(rows) > 0

    # ------------------------------------------------------------------
    # Query operations
    # ------------------------------------------------------------------

    def id_exists(self, id_value: str) -> bool:
        t = self._ibis_table()
        return t.filter(t._id == id_value).count().execute() > 0

    def find(self, query: FilterExpr = None, _at_most: int = 0, _order: dict = None) -> Iterable:
        t = self._ibis_table()
        if query is not None:
            pred = self._ibis_filter(query)
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
            pred = self._ibis_filter(query)
            if pred is not None:
                t = t.filter(pred)
        return t.count().execute()

    def max(self, trait_name: str, filter: FilterExpr = None) -> dict:
        t = self._ibis_table()
        if filter is not None:
            pred = self._ibis_filter(filter)
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
            pred = self._ibis_filter(filter)
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

    # fmt: off
    serializer_map = {
        datetime: lambda v: v.replace(tzinfo=None).isoformat(),
        bytes:    lambda v: b64encode(v).decode(),
    }
    caster_map = {
        int:   lambda col: ibis_ops.UnwrapJSONInt64(col).to_expr(),
        float: lambda col: ibis_ops.UnwrapJSONFloat64(col).to_expr(),
        bool:  lambda col: ibis_ops.UnwrapJSONBoolean(col).to_expr(),
    }
    # fmt: on

    @abc.abstractmethod
    def _execute(self, sql: str, params: list = ()) -> list[tuple]: ...

    class Transaction(TsStore.Transaction):
        def __init__(self, store: IbisStore):
            self._nested = store.current_transaction() is not None
            if not self._nested:
                store._execute('BEGIN')
            super().__init__(store)

        def _do_commit(self) -> None:
            if not self._nested:
                self.store._execute('COMMIT')

        def _do_abort(self) -> None:
            if not self._nested:
                try:
                    self.store._execute('ROLLBACK')
                except Exception:
                    pass
