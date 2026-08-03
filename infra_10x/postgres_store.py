from __future__ import annotations

import getpass
import hashlib
import json
import re
import socket
import ssl
import struct
from typing import TYPE_CHECKING

import ibis
from core_10x.resource import Resource
from core_10x.ts_store import TsDuplicateKeyError

from infra_10x.ibis_store import (
    _DATA,
    _ID,
    _REV,
    IbisStore,
)

# PostgreSQL NAMEDATALEN is 64 (63 usable bytes); long class-id collection names
# (and their ``#history`` siblings) must not truncate into the same physical table.
_PG_IDENT_MAX = 63
# Frontend/Backend protocol: StartupMessage protocol 3.0; SSLRequest code.
_PG_PROTOCOL_3_0 = 196608
_PG_SSL_REQUEST_CODE = 80877103
# AuthenticationRequest codes (see Postgres protocol docs).
_PG_AUTH_OK = 0

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime


class PostgresStore(IbisStore, resource_name='POSTGRES_DB'):
    """PostgreSQL-backed Ibis traitable store.

    ``TS_USER`` is stamped from the **server session user** (``current_user``), not the
    Resource username used only for connecting. ``_data`` is stored as JSONB so blob
    keys can be expression-indexed later.
    """

    s_with_auth = False
    s_supports_add_column_if_not_exists = True
    # Postgres has no bare DOUBLE type (DuckDB/ANSI alias); use DOUBLE PRECISION.
    s_ddl_types = {
        float: 'DOUBLE PRECISION',
    }
    s_instance_kwargs_map = IbisStore.s_instance_kwargs_map | {
        Resource.HOSTNAME_TAG: (Resource.HOSTNAME_TAG, 'localhost'),
        Resource.PORT_TAG: (Resource.PORT_TAG, 5432),
        Resource.DBNAME_TAG: (Resource.DBNAME_TAG, 'postgres'),
        Resource.SSL_TAG: (Resource.SSL_TAG, False),
    }

    def _ibis_connect(self):
        # Resource identity → ibis names (host/user/database); TS_USER uses SQL current_user.
        # autocommit=True so explicit BEGIN/COMMIT match DuckDB / IbisStore.Transaction.
        return ibis.postgres.connect(
            host=self.hostname,
            port=self.port,
            database=self.dbname,
            user=self.username,
            password=self.password,
            autocommit=True,
        )

    def _pg_sql(self, sql: str) -> str:
        """Rewrite shared ``?`` binds to psycopg ``%s`` (no ``?`` in our string literals)."""
        return sql.replace('?', '%s')

    def _physical_table_name(self, collection_name: str) -> str:
        """Map logical collection names to a ≤63-byte PostgreSQL identifier.

        Untruncated names are used as-is when they fit. Longer names (typical class-id
        paths and ``#history`` suffixes) get a stable hash so main vs history never collide.
        """
        raw = collection_name
        if len(raw.encode('utf-8')) <= _PG_IDENT_MAX:
            return raw
        digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]
        # Readable prefix from the tail (often the class short name / uuid).
        tail = re.sub(r'[^A-Za-z0-9_]+', '_', raw)[-20:].strip('_') or 't'
        # c_<20>_<32> = 2+20+1+32 = 55 bytes max.
        return f'c_{tail}_{digest}'[:_PG_IDENT_MAX]

    def _execute(self, sql: str, params: list = ()) -> list[tuple]:
        with self._con.cursor() as cur:
            cur.execute(self._pg_sql(sql), list(params) if params else None)
            if cur.description is None:
                return []
            return cur.fetchall()

    def _create_table_if_not_exists(self, collection_name: str) -> None:
        # JSONB (not TEXT): enables expression indexes on blob keys; empty blob is '{}'::jsonb.
        self._execute(
            f'CREATE TABLE IF NOT EXISTS {self._qname(collection_name)} ({_ID} VARCHAR PRIMARY KEY, {_REV} INTEGER NOT NULL, {_DATA} JSONB NOT NULL)'
        )

    def _drop_table(self, collection_name: str) -> None:
        self._execute(f'DROP TABLE IF EXISTS {self._qname(collection_name)}')

    def _insert_sql(
        self,
        collection_name: str,
        *,
        overwrite: bool,
        column_names: Iterable[str],
        column_value_sqls: list[str],
        data_sql: str = '?',
    ) -> str:
        col_names = list(column_names)
        assert len(col_names) == len(column_value_sqls), (
            f'_insert_sql: column_names ({len(col_names)}) and column_value_sqls ({len(column_value_sqls)}) length mismatch'
        )
        cols = [_ID, _REV, *col_names, _DATA]
        value_exprs = ['?', '?', *column_value_sqls, data_sql]

        def _col_sql(c: str) -> str:
            return c if c in (_ID, _REV, _DATA) else f'"{c}"'

        col_sql = ', '.join(_col_sql(c) for c in cols)
        values_sql = ', '.join(value_exprs)
        qname = self._qname(collection_name)
        insert = f'INSERT INTO {qname} ({col_sql}) VALUES ({values_sql})'
        if overwrite:
            set_parts = [f'{_col_sql(c)} = EXCLUDED.{_col_sql(c)}' for c in cols if c != _ID]
            insert = f'{insert} ON CONFLICT ({_ID}) DO UPDATE SET {", ".join(set_parts)}'
        return f'{insert} RETURNING {col_sql}'

    def _handle_insert_error(self, exc: BaseException, collection_name: str, id_val: str) -> None:
        try:
            from psycopg.errors import UniqueViolation
        except ImportError:  # pragma: no cover
            raise exc from None
        if isinstance(exc, UniqueViolation):
            raise TsDuplicateKeyError(collection_name, {_ID: id_val}) from exc
        raise exc

    def _server_time_col_sql_expr(self) -> str:
        # Naive UTC timestamp for real columns (matches DuckDB wire: no tzinfo).
        return "(clock_timestamp() AT TIME ZONE 'UTC')"

    def _server_time_sql_expr(self) -> str:
        # ISO-like string for datetime_trait in the JSONB blob (no % for psycopg pyformat).
        return f'to_char({self._server_time_col_sql_expr()}, \'YYYY-MM-DD"T"HH24:MI:SS.US\')'

    def _auth_user_sql_expr(self) -> str:
        # Server-side logged-in role — not Resource.username.
        return 'current_user'

    def _auth_user_sql_params(self) -> list:
        return []

    def _json_ts_merge_sql(self, obj_parts: list[str]) -> str:
        merge = f'jsonb_build_object({", ".join(obj_parts)})'
        return f'(CAST(? AS jsonb) || {merge})'

    def _decode_data(self, val) -> dict:
        # RETURNING/psycopg may yield a mapping; ibis→polars scans cast JSONB to string first.
        if val is None or val == '':
            return {}
        if isinstance(val, dict):
            return val
        return json.loads(val)

    def _prepare_ibis_table(self, table):
        # Polars cannot ingest JSONB yet; cast ``_data`` to string for scans (decode still works).
        if _DATA in table.schema():
            return table.mutate(**{_DATA: table[_DATA].cast('string')})
        return table

    def _index_expr(self, collection_name: str, field: str) -> str | None:
        """Physical columns or JSONB path on ``_data``."""
        if field in self._collection_columns(collection_name):
            return field if field in (_ID, _REV, _DATA) else f'"{field}"'
        # Expression index on blob key (phase-1 jsonb benefit).
        return f"({_DATA} ->> '{field}')"

    @classmethod
    def is_running_with_auth(cls, host_name: str, port: int = None) -> tuple:
        """Return ``(is_running, with_auth)`` for vault / store_from_uri routing.

        Conservative policy (prefer vault over false open access):

        * ``(True, False)`` — only if passwordless startup fully succeeds (ReadyForQuery).
        * ``(False, False)`` — only if TCP cannot reach host:port (refused / timeout / DNS).
        * ``(True, True)`` — any other outcome after TCP connects (auth challenge, ErrorResponse,
          SSL failure, non-PG service, truncated handshake, …) so callers try vault credentials.

        Uses map default ``dbname`` and the OS user in the StartupMessage.
        """
        if port is None:
            port = cls.s_instance_kwargs_map[cls.PORT_TAG][1]
        dbname = cls.s_instance_kwargs_map[cls.DBNAME_TAG][1]
        port = int(port)
        try:
            sock = socket.create_connection((host_name, port), timeout=3.0)
        except OSError:
            return False, False
        try:
            return cls._startup_auth_probe(sock, host=host_name, user=getpass.getuser(), database=dbname, timeout=3.0)
        except OSError:
            # TCP succeeded; handshake/SSL/protocol failed → treat as up + try vault.
            return True, True

    @staticmethod
    def _startup_auth_probe(sock: socket.socket, *, host: str, user: str, database: str, timeout: float = 3.0) -> tuple:
        """SSLRequest + StartupMessage on an already-connected socket → (is_running, with_auth)."""

        def _recv_exact(n: int) -> bytes:
            buf = bytearray()
            while len(buf) < n:
                chunk = sock.recv(n - len(buf))
                if not chunk:
                    raise ConnectionError('postgres closed during startup probe')
                buf.extend(chunk)
            return bytes(buf)

        sock.settimeout(timeout)
        try:
            # SSLRequest → 'S' (TLS) or 'N' (cleartext).
            sock.sendall(struct.pack('!II', 8, _PG_SSL_REQUEST_CODE))
            ssl_flag = _recv_exact(1)
            if ssl_flag == b'S':
                ctx = ssl.create_default_context()
                sock = ctx.wrap_socket(sock, server_hostname=host)
            elif ssl_flag != b'N':
                # Connected but not speaking PG SSL negotiation → up, not open.
                return True, True

            params = (
                b''.join(
                    k + b'\x00' + v + b'\x00'
                    for k, v in (
                        (b'user', user.encode()),
                        (b'database', database.encode()),
                        (b'client_encoding', b'UTF8'),
                    )
                )
                + b'\x00'
            )
            body = struct.pack('!I', _PG_PROTOCOL_3_0) + params
            sock.sendall(struct.pack('!I', 4 + len(body)) + body)

            # Trust: AuthenticationOk then Error (bad role). Open: AuthOk … ReadyForQuery.
            while True:
                tag = _recv_exact(1)
                length = struct.unpack('!I', _recv_exact(4))[0]
                payload = _recv_exact(length - 4) if length > 4 else b''
                if (result := PostgresStore._classify_startup_backend_message(tag, payload)) is not None:
                    return result
        finally:
            try:
                sock.close()
            except OSError:
                pass

    @staticmethod
    def _classify_startup_backend_message(tag: bytes, payload: bytes) -> tuple | None:
        """Map one backend message to a final result, or ``None`` to keep reading.

        Only ReadyForQuery after AuthenticationOk yields open access ``(True, False)``.
        Auth challenges and errors yield ``(True, True)`` (try vault).
        """
        if tag == b'R':  # Authentication*
            if len(payload) < 4:
                return True, True
            code = struct.unpack('!I', payload[:4])[0]
            return None if code == _PG_AUTH_OK else (True, True)
        if tag == b'Z':  # ReadyForQuery — fully accepted without a password challenge
            return True, False
        if tag == b'E':  # ErrorResponse
            return True, True
        # ParameterStatus (S), BackendKeyData (K), Notice (N), …
        return None

    def auth_user(self) -> str | None:
        rows = self._execute('SELECT current_user')
        return rows[0][0] if rows else None

    def server_time(self) -> datetime:
        rows = self._execute(f'SELECT {self._server_time_col_sql_expr()}')
        val = rows[0][0]
        return val.replace(tzinfo=None) if hasattr(val, 'tzinfo') and val.tzinfo else val
