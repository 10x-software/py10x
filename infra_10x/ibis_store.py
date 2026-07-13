from __future__ import annotations

import abc
import json
import re
from base64 import b64encode
from datetime import datetime
from typing import TYPE_CHECKING

import ibis
import ibis.expr.operations as ibis_ops

from core_10x.nucleus import Nucleus
from core_10x.trait_definition import T
from core_10x.ts_store import TS_FIELDS_TAG, TsCollection, TsDuplicateKeyError, TsStore

if TYPE_CHECKING:
    from collections.abc import Iterable

    from core_10x.trait_filter import f as FilterExpr  # noqa: N812


_ID  = Nucleus.ID_TAG()
_REV = Nucleus.REVISION_TAG()
_TS_TIME = T.TS_TIME.value()
_TS_USER = T.TS_USER.value()


# ---------------------------------------------------------------------------
# IbisCollection — shared ibis-based query logic
# ---------------------------------------------------------------------------


class IbisCollection(TsCollection):
    """Abstract base for ibis-backed collections.

    Shared DML (save / save_new / delete) and all read-path logic live here.
    Subclasses supply dialect hooks (insert SQL, unique-violation mapping) and DDL.
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

    def _handle_insert_error(self, exc: BaseException, id_val: str) -> None:
        """Map backend integrity errors to :class:`TsDuplicateKeyError`, else re-raise."""
        raise exc

    def _insert_sql(self, *, overwrite: bool, data_sql: str) -> str:
        """Dialect INSERT (or upsert) that binds ``(?, ?, {data_sql})`` and returns ``_rev, _data``."""
        raise NotImplementedError(f'{type(self).__name__} must implement _insert_sql')

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
            dt = getattr(trait, 'data_type', None)
            if not dt and hasattr(trait, 'serialize_to_type'):
                dt = trait.serialize_to_type()
            if dt and (fn := self._store.caster_map.get(dt)):
                return fn(col)
            if dt and dt in self._store.serializer_map:
                return ibis_ops.UnwrapJSONString(col).to_expr()

        unwrapped = ibis_ops.UnwrapJSONString(col).to_expr()
        raw_str = col.cast("string")
        return ibis.ifelse(raw_str == "null", ibis.null(), unwrapped.coalesce(raw_str))

    def ibis_right_value(self, value):
        if fn := self._store.serializer_map.get(type(value)):
            return fn(value)
        if isinstance(value, (dict, list)): # -- non-primitieve types are compared as strings
            # -- dict and list are the only non-primitive types since value is already passed trait serialization
            return json.dumps(value, separators=(",", ":"))
        return value

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

    # ------------------------------------------------------------------
    # DML operations
    # ------------------------------------------------------------------

    def _prepare_write(self, serialized_traitable: dict, *, rev: int | None = None):
        """Copy write map, pop ``_ts_fields``, build ``_data`` SQL/params.

        If ``rev`` is set (insert/upsert), forces that revision on the doc.
        """
        doc = dict(serialized_traitable)
        ts_fields = dict(doc.pop(TS_FIELDS_TAG, None) or {})
        if rev is not None:
            doc[_REV] = rev
        id_val = doc[_ID]
        assert id_val, f'{type(self).__name__} requires a non-empty {_ID}'
        rev = doc[_REV]
        data_json = json.dumps(
            {k: v for k, v in doc.items() if k not in (_ID, _REV)},
            default=self._json_encode_value,
        )
        data_sql, data_params = self._data_sql_and_params(data_json, ts_fields)
        return id_val, rev, ts_fields, data_sql, data_params

    def _save_sql(
        self,
        *,
        insert: bool = False,
        update: bool = False,
        upsert: bool = False,
        data_sql: str,
        data_params: list,
        id_val: str,
        rev: int,
    ) -> tuple[str, list]:
        """Build INSERT / INSERT OR REPLACE / optimistic UPDATE SQL and bind params."""
        if sum((insert, update, upsert)) != 1:
            raise ValueError('exactly one of insert, update, upsert must be true')
        if update:
            # Same merged expression for DISTINCT check and assignment (server stamps included).
            sql = (
                f'UPDATE {self._qname()} SET '
                f'{_REV} = CASE WHEN _data IS DISTINCT FROM ({data_sql}) THEN {_REV} + 1 ELSE {_REV} END, '
                f'_data = {data_sql} '
                f'WHERE {_ID} = ? AND {_REV} = ? '
                f'RETURNING {_REV}, _data'
            )
            return sql, [*data_params, *data_params, id_val, rev]
        sql = self._insert_sql(overwrite=upsert, data_sql=data_sql)
        return sql, [id_val, rev, *data_params]

    def _save(
        self,
        serialized_traitable: dict,
        *,
        insert: bool = False,
        update: bool = False,
        upsert: bool = False,
    ) -> dict:
        id_val, rev, ts_fields, data_sql, data_params = self._prepare_write(
            serialized_traitable, rev=1 if insert or upsert else None
        )
        sql, params = self._save_sql(
            insert=insert,
            update=update,
            upsert=upsert,
            data_sql=data_sql,
            data_params=data_params,
            id_val=id_val,
            rev=rev,
        )
        try:
            rows = self._execute(sql, params)
        except Exception as e:
            if insert or upsert:
                self._handle_insert_error(e, id_val)
            raise
        if not rows:
            detail = (
                f'rev {rev} no longer current'
                if update
                else f'no row returned for {_ID}={id_val!r}'
            )
            raise RuntimeError(f'{"Revision conflict" if update else "Write failed"} saving {id_val}: {detail}')
        new_rev, data_json = rows[0]
        assert new_rev == rev if insert or upsert else new_rev in (rev, rev + 1)
        if not ts_fields:
            return {_REV: new_rev}
        persisted = json.loads(data_json)
        return {_REV: new_rev, **{f: v for f in ts_fields if (v := persisted.get(f, persisted)) is not persisted}}

    def save_new(self, serialized_traitable: dict, overwrite: bool = False) -> dict:
        """Insert (or replace) in **one** round trip via dialect ``INSERT … RETURNING``."""
        return self._save(serialized_traitable, upsert=overwrite, insert=not overwrite)

    def save(self, serialized_traitable: dict) -> dict:
        """Optimistic save in **one** round trip (like Mongo ``find_one_and_update`` AFTER)."""
        if serialized_traitable[_REV] == 0:
            return self.save_new(serialized_traitable)
        return self._save(serialized_traitable, update=True)

    def _server_time_sql_expr(self) -> str:
        """SQL expression for a JSON-compatible server timestamp (dialect-specific)."""
        raise NotImplementedError(f'{type(self).__name__} must implement _server_time_sql_expr')

    def _auth_user_sql_expr(self) -> str:
        """SQL expression for auth user (default: bound parameter ``?``)."""
        return '?'

    def _auth_user_sql_params(self) -> list:
        return [self._store.auth_user()]

    def _data_sql_and_params(self, data_json: str, ts_fields: dict) -> tuple[str, list]:
        """SQL expression and bind params for the ``_data`` column (base JSON ± TS merge)."""
        if not ts_fields:
            return '?', [data_json]
        # json_merge_patch(base, json_object(field, expr, ...)) — exprs from dialect hooks.
        obj_parts: list[str] = []
        params: list = [data_json]
        for field, kind in ts_fields.items():
            safe = field.replace("'", "''")
            if kind == _TS_TIME:
                obj_parts.append(f"'{safe}', {self._server_time_sql_expr()}")
            else:  # TS_USER
                obj_parts.append(f"'{safe}', {self._auth_user_sql_expr()}")
                params.extend(self._auth_user_sql_params())
        merge = f"json_object({', '.join(obj_parts)})"
        return f'json_merge_patch(CAST(? AS JSON), {merge})', params


    def delete(self, id_value: str) -> bool:
        rows = self._execute(
            f'DELETE FROM {self._qname()} WHERE {_ID} = ? RETURNING {_ID}', [id_value]
        )
        return len(rows) > 0

    def _index_expr(self, field: str) -> str | None:
        """SQL expression for one index key, or ``None`` if this dialect cannot index ``field``.

        Default returns ``field`` as a bare column name so new dialects fail loudly in tests
        until they override (e.g. DuckDB only real columns; Postgres JSON path expressions).
        """
        return field

    def create_index(self, name: str, trait_name: str | list[tuple[str, int]], **index_args) -> str:
        """Create an index using dialect ``_index_expr`` for each key field.

        If any field is unsupported (``_index_expr`` returns ``None``), the call is a no-op
        and still returns ``name``.

        Honors ``unique=True`` (Mongo parity for :class:`~core_10x.traitable.Index` kwargs).
        Other Mongo-only ``index_args`` are ignored.
        """
        if isinstance(trait_name, list):
            parts: list[str] = []
            for field, direction in trait_name:
                expr = self._index_expr(field)
                if expr is None:
                    return name
                parts.append(f"{expr} {'DESC' if direction < 0 else 'ASC'}")
            cols = ', '.join(parts)
        else:
            expr = self._index_expr(trait_name)
            if expr is None:
                return name
            cols = expr

        unique = 'UNIQUE ' if index_args.get('unique') else ''
        safe_name = re.sub(r'[^A-Za-z0-9_]', '_', name)
        self._execute(
            f'CREATE {unique}INDEX IF NOT EXISTS {safe_name} ON {self._qname()} ({cols})'
        )
        return name

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
        str:   lambda col: ibis_ops.UnwrapJSONString(col).to_expr(),
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
