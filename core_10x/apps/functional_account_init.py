"""Automated Docker-wrapped provisioning for functional-account vault registration.

Installed by ``py10x-core`` as the ``xx-functional-account-init`` console script (see
``pyproject.toml``); also runnable directly as
``python -m core_10x.apps.functional_account_init``.

Runs ``xx-user-init --functional-account --output-file <fifo>`` inside a disposable
container (kernel-verified identity via ``docker/entrypoint.sh``; see
docs/VAULT_SECURITY_DESIGN.md §3.3), then feeds the manifest to a host-side
provisioning command over a bind-mounted FIFO, not a file.

``docker run -it`` (not stdout piping) keeps ``getpass`` prompts masked -- a pty is
required, and once one exists stdout and stderr are merged, so the manifest cannot
travel over stdout.

See ``docs/USER_ONBOARDING_AUTH.md``.
"""

from __future__ import annotations

import importlib.metadata
import os
import shlex
import subprocess
import sys
import tempfile
import threading

from core_10x.environment_variables import EnvVars
from core_10x.functional_account_keyring import FunctionalAccountKeyring
from core_10x.rc import RC, RC_TRUE
from core_10x.resource import Resource
from core_10x.trait_definition import RT
from core_10x.traitable import VaultUser
from core_10x.traitable_cli import TraitableCli

_IMAGE_REPO = 'ghcr.io/10x-software/py10x-core'
_CONTAINER_MOUNT_DIR = '/var/run/xx-provisioning-output'
_LOOPBACK_HOSTS = {'localhost', '127.0.0.1', '::1'}
# Owner read while this process opens the pipe, then owner write and no read bit.
# The container uid is not the owner until entrypoint.sh chowns, so the directory
# must be traversable by other. 0711 does not grant read or write of the pipe.
_FIFO_OWNER_READ = 0o400
_FIFO_OWNER_WRITE = 0o200
_PROVISIONING_DIR_MODE = 0o711


def _drain_provisioning_fifo(fd: int, writer_finished: threading.Event, holder: dict) -> None:
    """Read the manifest while the container writes.

    A nonblocking read returns ``b''`` both before any writer has opened the pipe
    and when the last writer closes. ``b''`` is end of stream only after ``docker run``
    has returned (``writer_finished``). Pipe capacity is a host setting (default 16
    pages, one page after ``pipe-user-pages-soft``), so this drains during the write.
    """
    chunks: list[bytes] = []
    try:
        while not writer_finished.is_set():
            try:
                chunk = os.read(fd, 65536)
            except BlockingIOError:
                writer_finished.wait(0.01)
                continue
            if chunk:
                chunks.append(chunk)
            else:
                writer_finished.wait(0.01)
        while True:
            try:
                chunk = os.read(fd, 65536)
            except BlockingIOError:
                break
            if not chunk:
                break
            chunks.append(chunk)
        if chunks:
            holder['payload'] = b''.join(chunks).decode()
    except (OSError, UnicodeError) as ex:
        holder['error'] = ex


class FunctionalAccountInitCli(TraitableCli):
    """Register a functional account end-to-end: run a real, disposable container (real
    kernel-verified OS identity via docker/entrypoint.sh's rename), then pipe its output to a
    provisioning command running outside the container.

    Usage:
    xx-functional-account-init --functional-account-id xx-myservice \\
        --command "docker secret create {secret_name} -"

    Image, vault URI, and network mode are auto-resolved -- pass --image-tag only when the
    currently-installed py10x-core version has no matching published image (e.g. an unreleased
    local dev version): --image-tag dev|pre|prod|<any specific tag>.
    --extra-docker-args appends further raw `docker run` args beyond what's auto-populated. If the
    value itself starts with "--" (e.g. "--memory 512m"), prefix it with a leading space (e.g.
    "--extra-docker-args ' --memory 512m'") -- TraitableCli's CLI parser otherwise treats a
    following "--"-prefixed token as the *next* option, not this one's value; the leading space
    survives shlex.split unaffected.
    """

    functional_account_id: str = RT('')
    image_tag: str = RT('')
    command: str = RT('')
    extra_docker_args: str = RT('')

    def post_verify(self) -> RC:
        rc = super().post_verify()
        if not self.functional_account_id:
            return rc + RC(False, '--functional-account-id is required')
        if not self.command:
            return rc + RC(False, '--command is required (the provisioning command run outside the container)')
        if not VaultUser.is_functional_account(self.functional_account_id):
            return rc + RC(
                False,
                f'--functional-account-id ({self.functional_account_id!r}) must start with the '
                f'functional-account prefix ({EnvVars.functional_account_prefix!r})',
            )
        return rc

    def _resolve_image(self) -> tuple[RC, str]:
        if self.image_tag:
            return RC_TRUE, f'{_IMAGE_REPO}:{self.image_tag}'

        version = importlib.metadata.version('py10x-core')
        image = f'{_IMAGE_REPO}:{version}'
        probe = subprocess.run(['docker', 'manifest', 'inspect', image], capture_output=True, check=False)
        if probe.returncode == 0:
            return RC_TRUE, image
        return (
            RC(
                False,
                f'no published image matches the running py10x-core version ({version}); pass --image-tag dev|pre|prod|<tag> explicitly',
            ),
            '',
        )

    def _resolve_docker_args(self) -> tuple[RC, list[str]]:
        vault_uri = EnvVars.main_vault_uri
        if not vault_uri:
            return (
                RC(
                    False,
                    'XX_MAIN_VAULT_URI must be set in this shell -- the container needs it to know which vault to register against',
                ),
                [],
            )

        args = ['-e', f'XX_MAIN_VAULT_URI={vault_uri}']
        if Resource.parse_uri(vault_uri).get(Resource.HOSTNAME_TAG) in _LOOPBACK_HOSTS:
            # A loopback vault host means "the vault runs on this same machine" -- unreachable
            # from inside a default-bridge container without this, same reasoning
            # .github/workflows/ci.yml's functional-account-e2e job already uses it for.
            args += ['--network', 'host']
        args += shlex.split(self.extra_docker_args)
        return RC_TRUE, args

    def run(self) -> RC:
        rc, image = self._resolve_image()
        if not rc:
            return rc
        rc, docker_args = self._resolve_docker_args()
        if not rc:
            return rc

        secret_name = FunctionalAccountKeyring.secret_name(self.functional_account_id)
        tmp_dir = tempfile.mkdtemp()
        os.chmod(tmp_dir, 0o700)
        fifo_name = self.functional_account_id.replace('/', '_').replace('\0', '_') + '.fifo'
        fifo_path = os.path.join(tmp_dir, fifo_name)
        os.mkfifo(fifo_path, _FIFO_OWNER_READ)
        os.chmod(fifo_path, _FIFO_OWNER_READ)  # mkfifo applies umask
        container_fifo_path = f'{_CONTAINER_MOUNT_DIR}/{fifo_name}'

        holder: dict = {}
        read_fd: int | None = None
        reader_thread: threading.Thread | None = None
        writer_finished = threading.Event()
        try:
            # Permission is checked at open. Hold the read fd, then drop the read bit
            # so a later open — including one by uid 10001 after the entrypoint chowns —
            # cannot take the stream. chmod of the directory lets that uid walk to the pipe.
            read_fd = os.open(fifo_path, os.O_RDONLY | os.O_NONBLOCK)
            os.chmod(fifo_path, _FIFO_OWNER_WRITE)
            os.chmod(tmp_dir, _PROVISIONING_DIR_MODE)
            reader_thread = threading.Thread(
                target=_drain_provisioning_fifo,
                args=(read_fd, writer_finished, holder),
                daemon=True,
                name='xx-functional-account-fifo',
            )
            reader_thread.start()

            docker_argv = [
                'docker',
                'run',
                '--rm',
                '-it',
                '-e',
                f'FUNCTIONAL_ACCOUNT_ID={self.functional_account_id}',
                '-v',
                f'{tmp_dir}:{_CONTAINER_MOUNT_DIR}',
                *docker_args,
                image,
                'xx-user-init',
                '--functional-account',
                '--output-file',
                container_fifo_path,
            ]
            # No stdio overrides: inherits this process's own terminal, so the container's
            # getpass prompts are masked exactly as if a human ran `docker run -it` directly.
            result = subprocess.run(docker_argv, check=False)
            writer_finished.set()
            reader_thread.join(timeout=10)
            if result.returncode != 0:
                return RC(False, f'docker run failed with exit code {result.returncode}')
            if reader_thread.is_alive():
                return RC(False, 'timed out reading the provisioning manifest')
            if 'error' in holder:
                return RC(False, f'failed to read manifest: {holder["error"]}')
            if 'payload' not in holder:
                return RC(False, 'container exited successfully but never wrote the manifest')
            payload = holder['payload']

            argv = shlex.split(self.command.format(secret_name=shlex.quote(secret_name)))
            try:
                subprocess.run(argv, input=payload, text=True, check=True)
            except (OSError, subprocess.CalledProcessError) as ex:
                return RC(False, f'--command failed: {ex}')
            print(f'seeded secret {secret_name!r} via: {self.command}', file=sys.stderr)

            return RC_TRUE
        finally:
            writer_finished.set()
            if reader_thread is not None and reader_thread.is_alive():
                reader_thread.join(timeout=10)
            if read_fd is not None:
                os.close(read_fd)
            try:
                os.remove(fifo_path)
            except OSError:
                pass
            try:
                os.rmdir(tmp_dir)
            except OSError:
                pass


if __name__ == '__main__':
    raise SystemExit(FunctionalAccountInitCli.main())
