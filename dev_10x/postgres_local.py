"""Local password-auth Postgres companion for infra_10x with-auth smoke tests.

Keeps the Brew (or other) trust instance on 5432 alone. Manages a second cluster on
port 5433 with a known password — same contract as CI ``setup-postgres``.

Usage (from repo root, venv prepared)::

    uv run --no-sync xx-postgres-local start
    uv run --no-sync xx-postgres-local status
    uv run --no-sync xx-postgres-local stop

Homebrew-only helper (``initdb`` / ``pg_ctl`` from ``postgresql@16`` or ``postgresql``).
Kernel-free: stdlib + subprocess only.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Shared with infra_10x password-auth smoke tests / CI setup-postgres defaults.
PASSWORD_AUTH_PORT = 5433
PASSWORD_AUTH_USER = 'postgres'
PASSWORD_AUTH_PASSWORD = 'py10x_pg_auth'
PASSWORD_AUTH_DB = 'postgres'
DEFAULT_DATA_DIR = Path.home() / 'pgdata-py10x-auth'


def _brew_pg_bin() -> Path | None:
    """Return ``…/bin`` for Homebrew postgresql@16 or postgresql, if present."""
    brew = shutil.which('brew')
    if not brew:
        return None
    for formula in ('postgresql@16', 'postgresql'):
        try:
            prefix = subprocess.check_output([brew, '--prefix', formula], text=True, stderr=subprocess.DEVNULL).strip()
        except subprocess.CalledProcessError:
            continue
        bin_dir = Path(prefix) / 'bin'
        if (bin_dir / 'initdb').is_file() and (bin_dir / 'pg_ctl').is_file():
            return bin_dir
    return None


def _resolve_bin(name: str, brew_bin: Path | None) -> str:
    if brew_bin is not None:
        candidate = brew_bin / name
        if candidate.is_file():
            return str(candidate)
    found = shutil.which(name)
    if found:
        return found
    raise SystemExit(f'{name} not found. Install Homebrew PostgreSQL (e.g. `brew install postgresql@16`) or put initdb/pg_ctl on PATH.')


def _ensure_port_config(data_dir: Path, port: int) -> None:
    conf = data_dir / 'postgresql.conf'
    text = conf.read_text() if conf.is_file() else ''
    lines = text.splitlines()
    out: list[str] = []
    saw_port = False
    saw_listen = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('port') and '=' in stripped and not stripped.startswith('#'):
            out.append(f'port = {port}')
            saw_port = True
            continue
        if stripped.startswith('listen_addresses') and '=' in stripped and not stripped.startswith('#'):
            out.append("listen_addresses = 'localhost'")
            saw_listen = True
            continue
        out.append(line)
    if not saw_port:
        out.append(f'port = {port}')
    if not saw_listen:
        out.append("listen_addresses = 'localhost'")
    conf.write_text('\n'.join(out) + '\n')


def _pg_ctl_status(pg_ctl: str, data_dir: Path) -> int:
    return subprocess.call([pg_ctl, '-D', str(data_dir), 'status'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _init_if_needed(initdb: str, data_dir: Path) -> None:
    if (data_dir / 'PG_VERSION').is_file():
        return
    # initdb requires an empty (or missing) data directory — keep the pwfile outside it.
    if data_dir.exists():
        leftover = sorted(p.name for p in data_dir.iterdir())
        # Stale `.pwfile` from an earlier failed start (written inside data_dir by mistake).
        if leftover == ['.pwfile']:
            (data_dir / '.pwfile').unlink(missing_ok=True)
        elif leftover:
            raise SystemExit(
                f'{data_dir} exists but is not a Postgres cluster and is not empty ({leftover!r}). '
                'Remove it or pass --data-dir, then retry `xx-postgres-local start`.'
            )
    else:
        data_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile('w', prefix='py10x-pg-auth-', suffix='.pw', delete=False) as fh:
        fh.write(PASSWORD_AUTH_PASSWORD + '\n')
        pw_path = Path(fh.name)
    try:
        pw_path.chmod(0o600)
        subprocess.check_call(
            [
                initdb,
                '-D',
                str(data_dir),
                '-U',
                PASSWORD_AUTH_USER,
                '--auth-local=trust',
                '--auth-host=scram-sha-256',
                f'--pwfile={pw_path}',
            ]
        )
    finally:
        pw_path.unlink(missing_ok=True)


def cmd_start(data_dir: Path, port: int) -> int:
    brew_bin = _brew_pg_bin()
    initdb = _resolve_bin('initdb', brew_bin)
    pg_ctl = _resolve_bin('pg_ctl', brew_bin)
    pg_isready = _resolve_bin('pg_isready', brew_bin)

    _init_if_needed(initdb, data_dir)
    _ensure_port_config(data_dir, port)

    if _pg_ctl_status(pg_ctl, data_dir) != 0:
        log = data_dir / 'logfile'
        subprocess.check_call([pg_ctl, '-D', str(data_dir), '-l', str(log), 'start'])

    deadline = time.time() + 30
    while time.time() < deadline:
        if (
            subprocess.call(
                [pg_isready, '-h', 'localhost', '-p', str(port), '-U', PASSWORD_AUTH_USER, '-d', PASSWORD_AUTH_DB],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            == 0
        ):
            print(f'password-auth Postgres ready on localhost:{port} (user={PASSWORD_AUTH_USER}, password={PASSWORD_AUTH_PASSWORD}, data={data_dir})')
            return 0
        time.sleep(0.5)
    print(f'Postgres did not become ready on localhost:{port}; see {data_dir / "logfile"}', file=sys.stderr)
    return 1


def cmd_stop(data_dir: Path) -> int:
    if not (data_dir / 'PG_VERSION').is_file():
        print(f'No cluster at {data_dir}')
        return 0
    brew_bin = _brew_pg_bin()
    pg_ctl = _resolve_bin('pg_ctl', brew_bin)
    if _pg_ctl_status(pg_ctl, data_dir) != 0:
        print(f'Already stopped ({data_dir})')
        return 0
    subprocess.check_call([pg_ctl, '-D', str(data_dir), 'stop', '-m', 'fast'])
    print(f'Stopped password-auth Postgres ({data_dir})')
    return 0


def cmd_status(data_dir: Path, port: int) -> int:
    brew_bin = _brew_pg_bin()
    pg_isready = _resolve_bin('pg_isready', brew_bin)
    running = (
        subprocess.call(
            [pg_isready, '-h', 'localhost', '-p', str(port), '-U', PASSWORD_AUTH_USER, '-d', PASSWORD_AUTH_DB],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        == 0
    )
    cluster = 'yes' if (data_dir / 'PG_VERSION').is_file() else 'no'
    print(f'cluster={cluster} data={data_dir}')
    print(f'listening={running} host=localhost port={port} user={PASSWORD_AUTH_USER} db={PASSWORD_AUTH_DB}')
    if running:
        print(f'password={PASSWORD_AUTH_PASSWORD}')
    return 0 if running else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description='Manage local password-auth Postgres for py10x infra tests (port 5433).')
    p.add_argument('command', choices=('start', 'stop', 'status'))
    p.add_argument(
        '--data-dir',
        type=Path,
        default=Path(os.environ.get('XX_PG_PASSWORD_AUTH_DATA', DEFAULT_DATA_DIR)),
        help=f'cluster data directory (default: {DEFAULT_DATA_DIR} or $XX_PG_PASSWORD_AUTH_DATA)',
    )
    p.add_argument(
        '--port',
        type=int,
        default=int(os.environ.get('XX_PG_PASSWORD_AUTH_PORT', PASSWORD_AUTH_PORT)),
        help=f'listen port (default: {PASSWORD_AUTH_PORT} or $XX_PG_PASSWORD_AUTH_PORT)',
    )
    args = p.parse_args(argv)
    data_dir = args.data_dir.expanduser().resolve()
    if args.command == 'start':
        return cmd_start(data_dir, args.port)
    if args.command == 'stop':
        return cmd_stop(data_dir)
    return cmd_status(data_dir, args.port)


if __name__ == '__main__':
    raise SystemExit(main())
