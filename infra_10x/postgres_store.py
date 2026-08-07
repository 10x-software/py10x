from __future__ import annotations

import getpass
import json
import socket
import ssl
import struct
from typing import TYPE_CHECKING
from urllib.parse import parse_qs

import ibis
import ibis.expr.datatypes as ibis_dtypes
import psycopg
from core_10x.global_cache import cache
from core_10x.resource import Resource
from core_10x.ts_store import TsDuplicateKeyError
from psycopg import sql
from psycopg.errors import UniqueViolation

from infra_10x.ibis_store import (
    _DATA,
    _ID,
    _REV,
    IbisStore,
)

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

    SSLMODE_TAG = 'sslmode'

    s_with_auth = False
    s_supports_add_column_if_not_exists = True
    # NAMEDATALEN is 64 → 63 usable bytes; long class-id / #history names must not collide.
    s_max_ident_bytes = 63
    # Postgres has no bare DOUBLE type (DuckDB/ANSI alias); use DOUBLE PRECISION.
    s_ddl_types = {
        float: 'DOUBLE PRECISION',
    }
    # JSONB, not JSON: ibis then emits jsonb casts, whose equality is *semantic* (key order and
    # spacing insensitive). Text comparison could never match — jsonb renormalizes on write.
    s_json_type = ibis_dtypes.JSON(binary=True)
    s_instance_kwargs_map = IbisStore.s_instance_kwargs_map | {
        Resource.HOSTNAME_TAG: (Resource.HOSTNAME_TAG, 'localhost'),
        Resource.PORT_TAG: (Resource.PORT_TAG, 5432),
        Resource.DBNAME_TAG: (Resource.DBNAME_TAG, 'postgres'),
        Resource.SSL_TAG: (Resource.SSL_TAG, False),
        SSLMODE_TAG: (SSLMODE_TAG, None),
    }

    @classmethod
    def parse_uri(cls, uri: str) -> dict:
        """Lift ``sslmode`` / ``ssl`` query params into Resource SSL + connect ``sslmode``."""
        kwargs = super().parse_uri(uri)
        query = kwargs.pop(cls.QUERY_TAG, None) or ''
        if not query:
            return kwargs
        qs = parse_qs(query, keep_blank_values=True)
        raw = (qs.get(cls.SSLMODE_TAG) or qs.get(cls.SSL_TAG) or [None])[0]
        if raw is None:
            return kwargs
        mode = str(raw).lower()
        if mode in ('require', 'verify-ca', 'verify-full'):
            kwargs[cls.SSL_TAG] = True
            kwargs[cls.SSLMODE_TAG] = mode
        elif mode in ('true', '1', 'yes'):
            kwargs[cls.SSL_TAG] = True
            kwargs[cls.SSLMODE_TAG] = 'require'
        elif mode in ('disable', 'false', '0', 'no'):
            kwargs[cls.SSL_TAG] = False
            kwargs[cls.SSLMODE_TAG] = 'disable'
        else:
            # prefer / allow / etc. — pass through without forcing SSL_TAG.
            kwargs[cls.SSLMODE_TAG] = mode
        return kwargs

    def __init__(self, hostname=None, dbname=None, username=None, password=None, **kwargs):
        # libpq-only; must be set before ``IbisStore.__init__`` opens the connection.
        self.sslmode = kwargs.get(self.SSLMODE_TAG)
        self._auth_user: str | None = None  # -- lazily resolved SQL current_user (see auth_user)
        super().__init__(hostname=hostname, dbname=dbname, username=username, password=password, **kwargs)

    def _ibis_connect(self):
        # Resource identity → ibis names (host/user/database); TS_USER uses SQL current_user.
        # autocommit=True so explicit BEGIN/COMMIT match DuckDB / IbisStore.Transaction.
        connect_kw = {
            'host': self.hostname,
            'port': self.port,
            'database': self.dbname,
            'user': self.username,
            'password': self.password,
            'autocommit': True,
        }
        mode = self.sslmode or ('require' if self.ssl else None)
        if mode:
            connect_kw[self.SSLMODE_TAG] = mode
        return ibis.postgres.connect(**connect_kw)

    @staticmethod
    def _rewrite_qmark_binds(sql: str) -> str:
        """Replace bind ``?`` with ``%s``.

        Leaves ``?`` inside single-quoted literals alone, and does not touch JSONB
        ``?|`` / ``?&`` operators. Bare JSONB ``?`` (key existence) still collides with
        binds — use ``->>`` / ``->`` instead (as ``_index_expr`` does).
        """
        out: list[str] = []
        i = 0
        in_str = False
        while i < len(sql):
            c = sql[i]
            if in_str:
                out.append(c)
                if c == "'" and i + 1 < len(sql) and sql[i + 1] == "'":
                    out.append("'")
                    i += 2
                    continue
                if c == "'":
                    in_str = False
                i += 1
                continue
            if c == "'":
                in_str = True
                out.append(c)
                i += 1
                continue
            if c == '?':
                nxt = sql[i + 1] if i + 1 < len(sql) else ''
                # Note: ``'' in '|&'`` is True in Python — require a real next char.
                if nxt and nxt in '|&':
                    out.append('?')
                else:
                    out.append('%s')
                i += 1
                continue
            out.append(c)
            i += 1
        return ''.join(out)

    def _pg_sql(self, sql: str) -> str:
        """Rewrite shared ``?`` binds to psycopg ``%s`` (string-literal aware)."""
        return self._rewrite_qmark_binds(sql)

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
        literal = collection_name.replace("'", "''")
        self._execute(f"COMMENT ON TABLE {self._qname(collection_name)} IS '{literal}'")

    def _catalog_collection_names(self) -> list[str]:
        """Logical names from the comment stamped by :meth:`_create_table_if_not_exists`.

        One query does both the comment lookup and the marker-column check, so listing a
        shared database does not scan every table in it. Un-stamped tables fall back to
        ``relname`` (a short name is its own physical name).
        """
        rows = self._execute(
            "SELECT c.relname, obj_description(c.oid, 'pg_class') "
            'FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace '
            "WHERE c.relkind = 'r' AND n.nspname = current_schema() "
            'AND (SELECT count(*) FROM pg_attribute a '
            '     WHERE a.attrelid = c.oid AND NOT a.attisdropped AND a.attname IN (?, ?, ?)) = 3',
            [_ID, _REV, _DATA],
        )
        return [comment or relname for relname, comment in rows]

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
        # Ibis maps dt.JSON -> pa.string() for every output format (pandas/polars/pyarrow alike;
        # see ibis.formats.pyarrow), and psycopg auto-decodes jsonb into dict/list before ibis
        # ever sees it — so this SQL-level CAST is what actually produces a string, not a
        # client-side re-serialization of an already-parsed dict. Not polars-specific and not
        # obviously avoidable without bypassing ibis for reads (see raw psycopg _execute path
        # used by inserts). Predicate pushdown still runs on the native jsonb column before this
        # cast, so it only touches the filtered/limited result set, not full-table scans.
        # TODO: revisit if profiling (see infra_10x/manual_tests/ postgres-vs-mongo perf test)
        # shows this cast is a measurable hot path for real query patterns.
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
    @cache
    def is_running_with_auth(cls, host_name: str, port: int = None) -> tuple:
        """Return ``(is_running, with_auth)`` for vault / store_from_uri routing.

        Deliberately speaks the v3 startup protocol on a raw socket instead of attempting a
        libpq connection: libpq silently supplies credentials from ``~/.pgpass``, ``PGPASSWORD``
        and service files, so a successful ``psycopg.connect()`` does **not** mean the server
        is open — it may just mean *this* machine has a stored password. That would report
        ``(True, False)``, skip the vault, and break for every other client. This probe never
        sends a password, so ``(True, False)`` means the server genuinely accepts unauthenticated
        logins. Do not "simplify" it into a connect-and-catch.

        Conservative policy (prefer vault over false open access):

        * ``(True, False)`` — only if passwordless startup fully succeeds (ReadyForQuery).
        * ``(False, False)`` — only if TCP cannot reach host:port (refused / timeout / DNS).
        * ``(True, True)`` — any other outcome after TCP connects (auth challenge, ErrorResponse,
          SSL failure, non-PG service, truncated handshake, …) so callers try vault credentials.

        Like Mongo, only ``host_name`` / ``port`` are inputs. The StartupMessage always uses
        the map-default ``dbname`` and the OS user (URI userinfo is ignored for the probe).
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

    @staticmethod
    def _qdb(dbname: str) -> str:
        return f'"{dbname.replace(chr(34), chr(34) * 2)}"'

    def list_databases(self, prefix: str = '') -> list[str]:
        return [r[0] for r in self._execute('SELECT datname FROM pg_database WHERE datname LIKE ? ORDER BY datname', [prefix + '%'])]

    def delete_database(self, dbname: str) -> bool:
        """``WITH (FORCE)`` (PG 13+) evicts other sessions, but libpq cannot drop the database
        this connection is attached to — hence the ``self.dbname`` guard."""
        if not dbname or dbname == self.dbname or not self._execute('SELECT 1 FROM pg_database WHERE datname = ?', [dbname]):
            return False
        self._execute(f'DROP DATABASE {self._qdb(dbname)} WITH (FORCE)')  # -- autocommit: no transaction block
        return True

    @classmethod
    def create_if_needed(cls, spec) -> bool:
        """Create the database in ``spec`` if absent, via the maintenance database. Needs CREATEDB."""
        dbname = spec.kwargs.get(cls.DBNAME_TAG)
        maintenance = cls.s_instance_kwargs_map[cls.DBNAME_TAG][1]
        if not dbname or dbname == maintenance:
            return False
        connect_kw = {
            'host': spec.hostname(),
            'port': spec.port(),
            'dbname': maintenance,
            'user': spec.kwargs.get(cls.USERNAME_TAG),
            'password': spec.kwargs.get(cls.PASSWORD_TAG),
        }
        with psycopg.connect(**{k: v for k, v in connect_kw.items() if v is not None}, autocommit=True) as con, con.cursor() as cur:
            cur.execute('SELECT 1 FROM pg_database WHERE datname = %s', [dbname])
            if cur.fetchone():
                return False
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(dbname)))
        return True

    def auth_user(self) -> str | None:
        # ``current_user`` is fixed for the life of the connection — query it once.
        if self._auth_user is None:
            rows = self._execute('SELECT current_user')
            self._auth_user = rows[0][0] if rows else None
        return self._auth_user

    def server_time(self) -> datetime:
        # ``AT TIME ZONE 'UTC'`` yields ``timestamp without time zone`` → psycopg returns naive.
        return self._execute(f'SELECT {self._server_time_col_sql_expr()}')[0][0]
