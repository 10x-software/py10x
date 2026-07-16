from __future__ import annotations

import abc
import json
import re
from base64 import b64encode
from datetime import date, datetime
from typing import TYPE_CHECKING

import ibis
import ibis.expr.operations as ibis_ops
from ibis.common.exceptions import TableNotFound

from core_10x.global_cache import cache
from core_10x.nucleus import Nucleus
from core_10x.trait import Trait
from core_10x.trait_definition import T
from core_10x.ts_store import TS_FIELDS_TAG, TsCollection, TsStore

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from core_10x.trait_filter import f as FilterExpr  # noqa: N812


_ID = Nucleus.ID_TAG()
_REV = Nucleus.REVISION_TAG()
_DATA = '_data'
_TS_TIME = T.TS_TIME.value()
_TS_USER = T.TS_USER.value()
_SCALAR_WIRE_TYPES = frozenset({str, int, float, bool, datetime, date, bytes})


class IbisCollection(TsCollection):
    """Ibis-backed collection (hybrid columns + JSON blob + add_ts). Dialect hooks live on the store."""

    s_id_tag = _ID

    def __init__(self, store: IbisStore, name: str, trait_dir: dict):
        self._store = store
        self._name = name
        self.col_trait_dir = {}
        self._update_trait_dir(trait_dir)

    def _update_trait_dir(self, trait_dir: dict) -> None:
        """Union column-eligible traits; names must be Python identifiers (used as SQL cols)."""
        assert all(tn.isidentifier() for tn in trait_dir), (
            f'Invalid trait_dir - names must be identifiers: {[tn for tn in trait_dir if not tn.isidentifier()]}'
        )
        self.col_trait_dir.update(
            (tn, t) for tn, t in trait_dir.items() if not t.flags_on(T.RUNTIME | T.RESERVED) and t.serialize_to_types() in _SCALAR_WIRE_TYPES
        )

    def collection_name(self) -> str:
        return self._name

    def _qname(self) -> str:
        return self._store._qname(self._name)

    def _execute(self, sql: str, params: list = ()) -> list[tuple]:
        return self._store._execute(sql, params)

    def _collection_columns(self) -> dict[str, type]:
        """Physical columns for this collection (``name → Python type``; empty if missing)."""
        return self._store._collection_columns(self._name)

    def intrinsic_trait_dir(self) -> dict[str, Trait]:
        return {col: Trait.create(col, T(data_type=typ)) for col, typ in self._collection_columns().items() if col not in (_ID, _REV, _DATA)}

    def _data_sql_and_params(self, data_json: str, ts_fields: dict) -> tuple[str, list]:
        """SQL expression and bind params for the ``_data`` column (base JSON ± TS merge)."""
        if not ts_fields:
            return '?', [data_json]
        obj_parts: list[str] = []
        params: list = [data_json]
        for field, kind in ts_fields.items():
            # field is a Python identifier (enforced in _update_trait_dir / reserved tags).
            if kind == _TS_TIME:
                obj_parts.append(f"'{field}', {self._store._server_time_sql_expr()}")
            else:  # TS_USER
                obj_parts.append(f"'{field}', {self._store._auth_user_sql_expr()}")
                params.extend(self._store._auth_user_sql_params())
        merge = f'json_object({", ".join(obj_parts)})'
        return f'json_merge_patch(CAST(? AS JSON), {merge})', params

    def ibis_col(self, name: str, trait=None):
        if (t := self._ibis_table_or_none()) is None:
            return ibis.null()
        if name in self._collection_columns():
            return t[name]
        trait = trait or self.col_trait_dir.get(name)
        col = t._data.cast('json')[name]
        if trait is not None:
            st = trait.serialize_to_types()
            if fn := self._store.json_caster_map.get(st):
                return fn(col)
            if st in self._store.json_serializer_map:
                return ibis_ops.UnwrapJSONString(col).to_expr()
        unwrapped = ibis_ops.UnwrapJSONString(col).to_expr()
        raw_str = col.cast('string')
        return ibis.ifelse(raw_str == 'null', ibis.null(), unwrapped.coalesce(raw_str))

    def ibis_right_value(self, value, field_name: str | None = None):
        """RHS encoding for filters: :attr:`col_serializer_map` vs :attr:`json_serializer_map`."""
        serializer_map = self._store.col_serializer_map if field_name in self._collection_columns() else self._store.json_serializer_map
        field_type = trait.serialize_to_types() if field_name and (trait := self.col_trait_dir.get(field_name)) is not None else type(value)
        if fn := serializer_map.get(field_type):
            return fn(value)
        if field_type in (dict, list):
            return json.dumps(value, separators=(',', ':'))
        return value

    def _json_encode_value(self, v):
        if fn := self._store.json_serializer_map.get(type(v)):
            return fn(v)
        raise TypeError(f'Object of type {type(v).__name__} is not JSON serializable')

    def _make_row_tuple(self, doc: dict) -> tuple[str, int, dict, str | None]:
        id_val = doc[_ID]
        rev = doc.get(_REV, 0)
        col_vals: dict = {}
        data: dict = {}
        table_cols = self._collection_columns()
        for k, v in doc.items():
            if k in (_ID, _REV):
                continue
            if k in self.col_trait_dir and k in table_cols:
                col_vals[k] = fn(v) if v is not None and (fn := self._store.col_serializer_map.get(self.col_trait_dir[k].serialize_to_types())) else v
                if v is None:
                    data[k] = None  # -- this way we can tell if the key was present when deserializing
            else:
                data[k] = v
        data_json = json.dumps(data, default=self._json_encode_value)
        return id_val, rev, col_vals, data_json

    def _decode_row(self, columns: Sequence[str], row: tuple) -> dict:
        """Map a physical row (polars / SQL RETURNING) to a traitable document dict."""
        col_doc = {}
        json_doc = {}
        for col, val in zip(columns, row, strict=True):
            if val is None:
                continue
            if col == _DATA:
                json_doc = json.loads(val)
                continue
            col_doc[col] = val
        return json_doc | col_doc

    def _hydrate(self, columns: Sequence[str], row: tuple, ts_fields: dict) -> dict:
        if not ts_fields:
            rev_idx = columns.index(_REV)
            return {_REV: row[rev_idx]}
        doc = self._decode_row(columns, row)
        return {_REV: doc[_REV], **{f: doc[f] for f in ts_fields if f in doc}}

    def _ensure_columns(self, columns: dict):
        self._store._ensure_columns(self._name, columns, self.col_trait_dir)

    def _prepare_write(self, doc: dict):
        self._store.ensure_table(self._name)
        ts_fields = doc.pop(TS_FIELDS_TAG, None) or {}
        # Promote columns for body keys and declared TS stamp fields.
        ensure_keys = {**doc, **{f: None for f in ts_fields}}
        self._ensure_columns(ensure_keys)

        # TS fields are stamped by the SQL server clock, never Python server_time():
        # as a column value SQL when the field is a real column, else merged into _data JSON.
        cols = self._collection_columns()  # reflects columns just promoted by _ensure_columns
        ts_col_exprs: dict[str, tuple[str, list]] = {}
        ts_for_json: dict = {}
        for field, kind in ts_fields.items():
            if field in cols:
                ts_col_exprs[field] = self._store._ts_col_sql_and_params(kind)
            else:
                ts_for_json[field] = kind

        id_val, rev_out, col_vals, data_json = self._make_row_tuple(doc)
        assert id_val, f'{type(self).__name__} requires a non-empty {_ID}'
        data_sql, data_params = self._data_sql_and_params(data_json, ts_for_json)
        # Ordered column write specs: regular columns bind a value, TS columns stamp via SQL.
        col_specs: dict[str, tuple[str, list]] = {c: ('?', [v]) for c, v in col_vals.items()}
        col_specs.update(ts_col_exprs)
        return id_val, rev_out, ts_fields, col_specs, data_sql, data_params

    def save_new(self, serialized_traitable: dict, overwrite: bool = False) -> dict:
        id_val, rev, ts_fields, col_specs, data_sql, data_params = self._prepare_write(serialized_traitable | {_REV: 1})
        column_names = list(col_specs)
        value_sqls = [vs for vs, _ in col_specs.values()]
        col_params = [p for _, ps in col_specs.values() for p in ps]
        try:
            rows = self._execute(
                self._store._insert_sql(
                    self._name,
                    overwrite=overwrite,
                    column_names=column_names,
                    column_value_sqls=value_sqls,
                    data_sql=data_sql,
                ),
                [id_val, rev, *col_params, *data_params],
            )
        except Exception as e:
            self._store._handle_insert_error(e, self._name, id_val)
            raise
        assert rows, f'{type(self).__name__}.save_new: INSERT returned no row for {_ID}={id_val!r}'
        return self._hydrate([_ID, _REV, *column_names, _DATA], rows[0], ts_fields)

    def save(self, serialized_traitable: dict) -> dict:
        rev = serialized_traitable[_REV]
        if rev == 0:
            return self.save_new(serialized_traitable)

        undef = next((k[1:] for k in serialized_traitable if k.startswith('$')), None)
        if undef:
            raise RuntimeError(f'Use of undefined variable: {undef}')

        id_val, rev, ts_fields, col_specs, data_sql, data_params = self._prepare_write(dict(serialized_traitable))

        # Apply new values only when something actually changes (chg in WHERE).
        # Binds once for SET and once for the change predicate — not per CASE column.
        # UPDATE + no-op/conflict SELECT must be atomic: nest in a store transaction
        # when the caller is not already inside one (e.g. non-history StorableHelper).
        set_clauses = [f'{_REV} = {_REV} + 1', *(f'"{c}" = {vs}' for c, (vs, _) in col_specs.items()), f'{_DATA} = ({data_sql})']
        chg = ' OR '.join((*(f'"{c}" IS DISTINCT FROM {vs}' for c, (vs, _) in col_specs.items()), f'{_DATA} IS DISTINCT FROM ({data_sql})'))
        ret_cols = [_REV, _DATA, *col_specs]
        returning = ', '.join([_REV, _DATA, *(f'"{c}"' for c in col_specs)])
        col_params = [p for spec in col_specs.values() for p in spec[1]]
        new_vals = [*col_params, *data_params]

        with self._store.transaction():
            rows = self._execute(
                f'UPDATE {self._qname()} SET {", ".join(set_clauses)} WHERE {_ID} = ? AND {_REV} = ? AND ({chg}) RETURNING {returning}',
                [*new_vals, id_val, rev, *new_vals],
            )
            if rows:
                result = self._hydrate(ret_cols, rows[0], ts_fields)
                assert result[_REV] == rev + 1
                return result

            # No row updated: either nothing changed (same rev) or optimistic-lock conflict.
            rows = self._execute(
                f'SELECT {returning} FROM {self._qname()} WHERE {_ID} = ? AND {_REV} = ?',
                [id_val, rev],
            )
            if not rows:
                raise RuntimeError(f'Revision conflict saving {id_val}: rev {rev} no longer current')
            result = self._hydrate(ret_cols, rows[0], ts_fields)
            assert result[_REV] == rev
            return result

    def delete(self, id_value: str) -> bool:
        if not self._collection_columns():
            return False
        rows = self._execute(f'DELETE FROM {self._qname()} WHERE {_ID} = ? RETURNING {_ID}', [id_value])
        return len(rows) > 0

    def create_index(self, name: str, trait_name: str | list[tuple[str, int]], **index_args) -> str:
        # Index DDL is dialect-specific; the store owns it so a store can override
        # indexing wholesale (JSON-path indexes, or a no-op on schemaless stores).
        return self._store.create_index(self._name, name, trait_name, self.col_trait_dir, **index_args)

    def _ibis_table_or_none(self):
        """Ibis table, or None if missing (and drop a stale column cache after rollback)."""
        if not self._collection_columns():
            return None
        try:
            return self._store._ibis_con.table(self._name)
        except TableNotFound:
            # CREATE TABLE rolled back (or table dropped) while @cache still held schema.
            self._store._forget_collection_columns(self._name)
            return None

    def id_exists(self, id_value: str) -> bool:
        if (t := self._ibis_table_or_none()) is None:
            return False
        return t.filter(t._id == id_value).count().execute() > 0

    def find(self, query: FilterExpr = None, _at_most: int = 0, _order: dict = None) -> Iterable:
        if (t := self._ibis_table_or_none()) is None:
            return
        if query is not None:
            pred = query.ibis(ibis_collection=self)
            if pred is not None:
                t = t.filter(pred)
        if _order:
            sort_keys = []
            for field, direction in _order.items():
                col = self.ibis_col(field)
                sort_keys.append(col.asc() if direction >= 0 else col.desc())
            t = t.order_by(sort_keys)
        if _at_most > 0:
            t = t.limit(_at_most)
        df = t.to_polars()
        if df.is_empty():
            return
        cols = df.columns
        for row in df.iter_rows():
            yield self._decode_row(cols, row)

    def count(self, query: FilterExpr = None) -> int:
        if (t := self._ibis_table_or_none()) is None:
            return 0
        if query is not None:
            pred = query.ibis(ibis_collection=self)
            if pred is not None:
                t = t.filter(pred)
        return int(t.count().execute())

    def max(self, trait_name: str, filter: FilterExpr = None) -> dict:
        if (t := self._ibis_table_or_none()) is None:
            return {}
        if filter is not None:
            pred = filter.ibis(ibis_collection=self)
            if pred is not None:
                t = t.filter(pred)
        col = self.ibis_col(trait_name)
        df = t.order_by(col.desc()).limit(1).to_polars()
        if df.is_empty():
            return {}
        return self._decode_row(df.columns, df.row(0))

    def min(self, trait_name: str, filter: FilterExpr = None) -> dict:
        if (t := self._ibis_table_or_none()) is None:
            return {}
        if filter is not None:
            pred = filter.ibis(ibis_collection=self)
            if pred is not None:
                t = t.filter(pred)
        col = self.ibis_col(trait_name)
        df = t.order_by(col.asc()).limit(1).to_polars()
        if df.is_empty():
            return {}
        return self._decode_row(df.columns, df.row(0))


class IbisStore(TsStore):
    """Abstract base for ibis-backed stores (DuckDB, Postgres, …).

    Concrete stores implement dialect hooks here; :class:`IbisCollection` is shared.
    """

    s_requires_schema = True
    s_supports_add_column_if_not_exists: bool = False
    s_ddl_types: dict[type, str] = {
        str: 'VARCHAR',
        int: 'BIGINT',
        float: 'DOUBLE',
        bool: 'BOOLEAN',
        datetime: 'TIMESTAMP',
        date: 'DATE',
        bytes: 'VARCHAR',
    }

    # JSON field → typed ibis expr (filter LHS on blob path).
    json_caster_map = {
        str: lambda col: ibis_ops.UnwrapJSONString(col).to_expr(),
        int: lambda col: ibis_ops.UnwrapJSONInt64(col).to_expr(),
        float: lambda col: ibis_ops.UnwrapJSONFloat64(col).to_expr(),
        bool: lambda col: ibis_ops.UnwrapJSONBoolean(col).to_expr(),
    }
    # Python value → native SQL bind (TIMESTAMP / DATE / b64 text in VARCHAR, …).
    col_serializer_map = {
        datetime: lambda v: v.replace(tzinfo=None),
        bytes: lambda v: b64encode(v).decode(),
    }
    # Python value → JSON wire (``_data`` blob and JSON-path filter RHS).
    json_serializer_map = col_serializer_map | {
        datetime: lambda v: v.replace(tzinfo=None).isoformat(),
    }

    def __init__(self):
        super().__init__()
        self._collections: dict[str, IbisCollection] = {}

    def __init_subclass__(cls, **kwargs):
        if 's_ddl_types' in cls.__dict__:
            parent_types = {}
            for base in cls.__bases__:
                if issubclass(base, IbisStore):
                    parent_types = dict(base.s_ddl_types)
                    break
            cls.s_ddl_types = {**parent_types, **cls.__dict__['s_ddl_types']}
        super().__init_subclass__(**kwargs)

    @abc.abstractmethod
    def _execute(self, sql: str, params: list = ()) -> list[tuple]: ...

    def _qname(self, collection_name: str) -> str:
        """Quoted table identifier for SQL (ANSI double quotes; dialect may override)."""
        return f'"{collection_name.replace(chr(34), chr(34) * 2)}"'

    @abc.abstractmethod
    def _create_table_if_not_exists(self, collection_name: str) -> None: ...

    @abc.abstractmethod
    def _drop_table(self, collection_name: str) -> None: ...

    @abc.abstractmethod
    def _insert_sql(
        self,
        collection_name: str,
        *,
        overwrite: bool,
        column_names: Iterable[str],
        column_value_sqls: list[str],
        data_sql: str = '?',
    ) -> str:
        """Dialect-specific INSERT (or INSERT OR REPLACE) with RETURNING (always includes ``_data``)."""

    def _handle_insert_error(self, exc: BaseException, collection_name: str, id_val: str) -> None:
        """Map dialect constraint errors to :class:`TsDuplicateKeyError`; re-raise otherwise."""
        raise exc

    @abc.abstractmethod
    def _server_time_sql_expr(self) -> str:
        """SQL expression for a JSON-compatible server timestamp (dialect-specific)."""

    @abc.abstractmethod
    def _server_time_col_sql_expr(self) -> str:
        """SQL expression for a server timestamp as a native column value (dialect-specific)."""

    @abc.abstractmethod
    def _auth_user_sql_expr(self) -> str:
        """SQL expression for the acting user in JSON (dialect-specific; may be a bind ``?``)."""

    @abc.abstractmethod
    def _auth_user_sql_params(self) -> list:
        """Bind params for :meth:`_auth_user_sql_expr` (empty if the expr is pure SQL)."""

    def _ts_col_sql_and_params(self, kind: str) -> tuple[str, list]:
        """Value SQL (+ binds) that stamps a TS **column** server-side (``TS_TIME`` / ``TS_USER``)."""
        if kind == _TS_TIME:
            return self._server_time_col_sql_expr(), []
        return self._auth_user_sql_expr(), self._auth_user_sql_params()

    @cache
    def _collection_columns(self, collection_name: str) -> dict[str, type]:
        """Catalog lookup: column name → Python type. Empty dict if the table is missing.

        Cached via :func:`core_10x.global_cache.cache`. Callers that mutate schema must
        either update the returned dict in place (ADD COLUMN) or
        :meth:`_forget_collection_columns` (create after sticky empty / drop).
        """
        try:
            schema = self._ibis_con.table(collection_name).limit(0).to_polars().schema
        except TableNotFound:
            return {}
        return {name: dtype.to_python() for name, dtype in schema.items()}

    def _forget_collection_columns(self, collection_name: str) -> None:
        """Drop the ``@cache`` entry for ``collection_name`` (e.g. after CREATE / DROP)."""
        self._collection_columns.cache.pop((self, collection_name), None)

    def _forget_all_collection_columns(self) -> None:
        """Drop all ``@cache`` column maps for this store (e.g. after ROLLBACK of DDL)."""
        cache = self._collection_columns.cache
        for key in list(cache):
            if key and key[0] is self:
                del cache[key]

    def collection_names(self, regexp: str = None) -> list:
        # Only collections with a physical table (lazy DDL: open alone does not create one).
        names = sorted(n for n in self._collections if self._collection_columns(n))
        if regexp:
            pattern = re.compile(regexp)
            names = [n for n in names if pattern.match(n)]
        return names

    def collection(self, collection_name: str, trait_dir: dict) -> IbisCollection:
        """Return a collection handle. Physical table is created on first write / index."""
        if (coll := self._collections.get(collection_name)) is None:
            coll = self._collections[collection_name] = IbisCollection(self, collection_name, trait_dir)
        elif trait_dir:
            # Bundle members (and other late openers): union column-eligible traits.
            coll._update_trait_dir(trait_dir)
        return coll

    def delete_collection(self, collection_name: str) -> bool:
        """Drop the physical table (if any) and forget any cached handle / column map."""
        if known := collection_name in self._collections or bool(self._collection_columns(collection_name)):
            self._drop_table(collection_name)
            self._forget_collection_columns(collection_name)
            self._collections.pop(collection_name, None)
        return known

    def ensure_table(self, collection_name) -> None:
        """Create the physical table on first need (idempotent; Mongo-like lazy create)."""
        if self._collection_columns(collection_name):
            return
        self._create_table_if_not_exists(collection_name)
        self._forget_collection_columns(collection_name)
        assert self._collection_columns(collection_name), f'failed to create table {collection_name!r}'

    def _index_expr(self, collection_name: str, field: str) -> str | None:
        """SQL index key expression for ``field`` on ``collection_name``, or None if not indexable.

        Default: only physical columns are indexable. Dialects that can index JSON
        paths (e.g. Postgres ``_data->>'field'``) override this.
        """
        return f'"{field}"' if field in self._collection_columns(collection_name) else None

    def _ensure_columns(self, collection_name: str, keys: Iterable, col_trait_dir: dict) -> None:
        """Promote column-eligible fields to real SQL columns when the dialect allows."""
        if not self.s_supports_add_column_if_not_exists:
            return
        cols = self._collection_columns(collection_name)
        for key in keys:
            if key in cols or (trait := col_trait_dir.get(key)) is None:
                continue

            ddl = self.s_ddl_types.get(typ := trait.serialize_to_types(), 'VARCHAR')
            self._execute(f'ALTER TABLE {self._qname(collection_name)} ADD COLUMN IF NOT EXISTS "{key}" {ddl}')
            cols[key] = typ

    def create_index(self, collection_name: str, name: str, trait_name: str | list[tuple[str, int]], col_trait_dir: dict, **index_args) -> str:
        """Create an index on ``collection_name`` using physical columns.

        Column-eligible traits are promoted first (so ``s_indices`` on first save works
        before any row write). Raises if a field cannot be a real column (JSON-only). Stores that index differently (JSON paths) or cannot index
        at all (schemaless) override this.
        """
        self.ensure_table(collection_name)
        fields = [f for f, _ in trait_name] if isinstance(trait_name, list) else [trait_name]
        # Promote index keys that are column-eligible but not yet ALTERed.
        self._ensure_columns(collection_name, dict.fromkeys(fields), col_trait_dir)

        def _require_expr(field: str) -> str:
            expr = self._index_expr(collection_name, field)
            if expr is None:
                raise ValueError(f'{type(self).__name__} cannot index {field!r} on {collection_name}: not a physical column')
            return expr

        if isinstance(trait_name, list):
            cols = ', '.join(f'{_require_expr(field)} {"DESC" if direction < 0 else "ASC"}' for field, direction in trait_name)
        else:
            cols = _require_expr(trait_name)

        unique = 'UNIQUE ' if index_args.get('unique') else ''
        safe_name = re.sub(r'[^A-Za-z0-9_]', '_', name)
        self._execute(f'CREATE {unique}INDEX IF NOT EXISTS {safe_name} ON {self._qname(collection_name)} ({cols})')
        return name

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
                # CREATE TABLE / ALTER may have been rolled back; drop sticky schema cache.
                self.store._forget_all_collection_columns()
