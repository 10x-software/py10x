from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import duckdb
import ibis

from core_10x.ibis_store import IbisCollection, IbisStore, _ID, _REV, _json_encode
from core_10x.resource import Resource
from core_10x.ts_store import TsDuplicateKeyError


# ---------------------------------------------------------------------------
# DuckIbisCollection — DuckDB-specific DML, DDL, and ibis table access
# ---------------------------------------------------------------------------


class DuckIbisCollection(IbisCollection):
    def __init__(self, store: DuckIbisStore, name: str):
        self._store = store
        self._name = name
        self._con = store._con
        self._ibis_con = store._ibis_con

    def collection_name(self) -> str:
        return self._name

    def _qname(self) -> str:
        return f'"{self._name}"'

    def _ibis_table(self):
        return self._ibis_con.table(self._name)

    def save_new(self, serialized_traitable: dict, overwrite: bool = False) -> int:
        doc = dict(serialized_traitable)
        doc[_REV] = 1
        id_val, rev, data_json = self._encode_doc(doc)
        if not id_val:
            return 0
        try:
            if overwrite:
                self._con.execute(
                    f'INSERT OR REPLACE INTO {self._qname()} ({_ID}, {_REV}, _data) VALUES (?, ?, ?)',
                    [id_val, rev, data_json],
                )
            else:
                self._con.execute(
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

        row = self._con.execute(
            f'SELECT {_REV}, _data FROM {self._qname()} WHERE {_ID} = ?', [id_val]
        ).fetchone()
        if row:
            existing_rev, existing_data_json = row
            assert existing_rev == rev, f'Revision mismatch for {id_val}: expected {rev}, got {existing_rev}'
            if existing_data_json == new_data_json:
                return rev

        new_rev = rev + 1
        self._con.execute(
            f'UPDATE {self._qname()} SET {_REV} = ?, _data = ? WHERE {_ID} = ? AND {_REV} = ?',
            [new_rev, new_data_json, id_val, rev],
        )
        return new_rev

    def delete(self, id_value: str) -> bool:
        rows = self._con.execute(
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
            self._con.execute(f'CREATE INDEX IF NOT EXISTS {safe_name} ON {self._qname()} ({cols})')
        except Exception:
            pass  # some expressions cannot be indexed; silently skip
        return name


# ---------------------------------------------------------------------------
# DuckIbisStore — DuckDB-specific store lifecycle and transactions
# ---------------------------------------------------------------------------


class DuckIbisStore(IbisStore, resource_name='DUCK_DB'):
    """In-memory DuckDB-backed store for testing."""

    s_with_auth = False

    class Transaction(IbisStore.Transaction):
        def __init__(self, store: DuckIbisStore):
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
        self._con = duckdb.connect()
        self._ibis_con = ibis.duckdb.from_connection(self._con)
        self._collections: dict[str, DuckIbisCollection] = {}
        self.username = kwargs.get(Resource.USERNAME_TAG, 'test_user')
        self.dbname = kwargs.get(Resource.DBNAME_TAG)

    @classmethod
    def standard_key(cls, *args, username=None, **kwargs) -> tuple:
        return super().standard_key(*args, **kwargs)

    @classmethod
    def new_instance(cls, *args, **kwargs) -> DuckIbisStore:
        return cls(*args, **kwargs)

    def collection_names(self, regexp: str = None) -> list:
        names = sorted(self._collections.keys())
        if regexp:
            pattern = re.compile(regexp)
            names = [n for n in names if pattern.match(n)]
        return names

    def collection(self, collection_name: str) -> DuckIbisCollection:
        name = collection_name
        if name not in self._collections:
            safe = name.replace('"', '""')
            self._con.execute(
                f'CREATE TABLE IF NOT EXISTS "{safe}" '
                f'({_ID} VARCHAR PRIMARY KEY, {_REV} INTEGER NOT NULL, _data VARCHAR NOT NULL)'
            )
            self._collections[name] = DuckIbisCollection(self, name)
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

    def add_who(self, field: str, serialized_data: dict) -> dict:
        if field in serialized_data:
            raise RuntimeError(f'Field {field} is already in use.')
        serialized_data['_who'] = self.auth_user()
        return serialized_data

    def add_when(self, field: str, serialized_data: dict) -> dict:
        if field in serialized_data:
            raise RuntimeError(f'Field {field} is already in use.')
        serialized_data[field] = self.server_time()
        return serialized_data

    @classmethod
    def parse_uri(cls, uri: str) -> dict:
        # duckdb://hostname:port/dbname  or  duckdb://hostname/dbname
        from urllib.parse import urlsplit

        p = urlsplit(uri)
        result = {
            cls.HOSTNAME_TAG: p.hostname or '',
            cls.DBNAME_TAG: p.path.lstrip('/') or None,
        }
        if p.port:
            result[cls.PORT_TAG] = p.port
        if p.username:
            result[cls.USERNAME_TAG] = p.username
        return result


# backward-compatibility aliases
DuckDbStore = DuckIbisStore
DuckDbCollection = DuckIbisCollection
