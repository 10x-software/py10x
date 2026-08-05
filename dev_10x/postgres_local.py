"""Local password-auth Postgres companion for infra_10x with-auth smoke tests.

Keeps the trust instance on 5432 alone. Manages a second cluster on port 5433 with a
known password — same contract as CI ``setup-postgres``. Prefers Docker (a
``postgres:{DOCKER_PG_VERSION}`` container, mirroring CI) when the Docker daemon is
reachable; falls back to a Homebrew-managed cluster (``initdb`` / ``pg_ctl`` from
``postgresql@16`` or ``postgresql``) otherwise. Whichever backend was reachable at
``start`` is also what ``stop`` / ``status`` check.

Usage (from repo root, venv prepared)::

    uv run --no-sync xx-test-postgres-auth start
    uv run --no-sync xx-test-postgres-auth status
    uv run --no-sync xx-test-postgres-auth stop

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
# Not a real credential: a throwaway local test fixture, overridable via env so it never
# needs to be hardcoded for anyone who wants a non-default value.
PASSWORD_AUTH_PORT = 5433
PASSWORD_AUTH_USER = 'postgres'
PASSWORD_AUTH_PASSWORD = os.environ.get('XX_PG_PASSWORD_AUTH_PASSWORD', 'py10x_pg_auth')
PASSWORD_AUTH_DB = 'postgres'
DEFAULT_DATA_DIR = Path.home() / 'pgdata-py10x-auth'  # Homebrew fallback only.
DOCKER_CONTAINER_NAME = 'py10x-postgres-auth-local'
DOCKER_VOLUME_NAME = 'py10x-postgres-auth-local-data'
DOCKER_PG_VERSION = '15'  # matches .github/actions/setup-postgres default


# --- Docker backend --------------------------------------------------------------------


def _docker_bin() -> str | None:
    """Return the ``docker`` executable path if the CLI is on PATH and the daemon is reachable."""
    docker = shutil.which('docker')
    if not docker:
        return None
    try:
        subprocess.run([docker, 'info'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    return docker


def _container_state(docker: str, name: str) -> str | None:
    """Return docker's ``.State.Status`` (e.g. ``running``, ``exited``), or None if no such container."""
    try:
        out = subprocess.check_output([docker, 'inspect', '--format', '{{.State.Status}}', name], stderr=subprocess.DEVNULL, text=True)
    except subprocess.CalledProcessError:
        return None
    return out.strip()


def _container_host_port(docker: str, name: str) -> str | None:
    try:
        out = subprocess.check_output(
            [docker, 'inspect', '--format', '{{(index (index .NetworkSettings.Ports "5432/tcp") 0).HostPort}}', name],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None
    return out.strip() or None


def _docker_start(docker: str, port: int) -> int:
    name = DOCKER_CONTAINER_NAME
    state = _container_state(docker, name)
    if state is not None and _container_host_port(docker, name) != str(port):
        # --port changed since this container was created; recreate with the new mapping
        # (named volume survives, so data isn't lost).
        subprocess.check_call([docker, 'rm', '-f', name])
        state = None

    if state is None:
        subprocess.check_call(
            [
                docker,
                'run',
                '-d',
                '--name',
                name,
                '-e',
                'POSTGRES_HOST_AUTH_METHOD=scram-sha-256',
                '-e',
                f'POSTGRES_USER={PASSWORD_AUTH_USER}',
                '-e',
                f'POSTGRES_PASSWORD={PASSWORD_AUTH_PASSWORD}',
                '-e',
                f'POSTGRES_DB={PASSWORD_AUTH_DB}',
                '-v',
                f'{DOCKER_VOLUME_NAME}:/var/lib/postgresql/data',
                '-p',
                f'{port}:5432',
                f'postgres:{DOCKER_PG_VERSION}',
            ]
        )
    elif state != 'running':
        subprocess.check_call([docker, 'start', name])

    deadline = time.time() + 30
    while time.time() < deadline:
        if (
            subprocess.call(
                [docker, 'exec', name, 'pg_isready', '-U', PASSWORD_AUTH_USER, '-d', PASSWORD_AUTH_DB],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            == 0
        ):
            print(
                f'password-auth Postgres ready on localhost:{port} (user={PASSWORD_AUTH_USER}, password={PASSWORD_AUTH_PASSWORD}, docker container={name})'
            )
            return 0
        time.sleep(0.5)
    print(f'Postgres did not become ready on localhost:{port}; see `docker logs {name}`', file=sys.stderr)
    return 1


def _docker_stop(docker: str) -> int:
    name = DOCKER_CONTAINER_NAME
    state = _container_state(docker, name)
    if state is None:
        print(f'No Docker container named {name}')
        return 0
    if state != 'running':
        print(f'Already stopped ({name})')
        return 0
    subprocess.check_call([docker, 'stop', name])
    print(f'Stopped password-auth Postgres (docker container {name})')
    return 0


def _docker_status(docker: str, port: int) -> int:
    name = DOCKER_CONTAINER_NAME
    state = _container_state(docker, name)
    running = state == 'running'
    print(f'cluster={"yes" if state is not None else "no"} docker container={name}')
    print(f'listening={running} host=localhost port={port} user={PASSWORD_AUTH_USER} db={PASSWORD_AUTH_DB}')
    if running:
        print(f'password={PASSWORD_AUTH_PASSWORD}')
    return 0 if running else 1


# --- Homebrew fallback -------------------------------------------------------------------


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
    raise SystemExit(f'{name} not found. Install Docker, or Homebrew PostgreSQL (e.g. `brew install postgresql@16`), or put initdb/pg_ctl on PATH.')


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
                'Remove it or pass --data-dir, then retry `xx-test-postgres-auth start`.'
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


def _homebrew_start(data_dir: Path, port: int) -> int:
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


def _homebrew_stop(data_dir: Path) -> int:
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


def _homebrew_status(data_dir: Path, port: int) -> int:
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


# --- Dispatch --------------------------------------------------------------------------


def cmd_start(data_dir: Path, port: int) -> int:
    if (docker := _docker_bin()) is not None:
        return _docker_start(docker, port)
    return _homebrew_start(data_dir, port)


def cmd_stop(data_dir: Path) -> int:
    if (docker := _docker_bin()) is not None:
        return _docker_stop(docker)
    return _homebrew_stop(data_dir)


def cmd_status(data_dir: Path, port: int) -> int:
    if (docker := _docker_bin()) is not None:
        return _docker_status(docker, port)
    return _homebrew_status(data_dir, port)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog='xx-test-postgres-auth', description='Manage local password-auth Postgres for py10x infra tests (port 5433).')
    p.add_argument('command', choices=('start', 'stop', 'status'))
    p.add_argument(
        '--data-dir',
        type=Path,
        default=Path(os.environ.get('XX_PG_PASSWORD_AUTH_DATA', DEFAULT_DATA_DIR)),
        help=f'Homebrew fallback cluster data directory, ignored under Docker (default: {DEFAULT_DATA_DIR} or $XX_PG_PASSWORD_AUTH_DATA)',
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
