"""Automated Docker-wrapped provisioning for functional-account vault registration.

Installed by ``py10x-core`` as the ``xx-functional-account-init`` console script (see
``pyproject.toml``); also runnable directly as
``python -m core_10x.apps.functional_account_init``.

Runs ``xx-user-init --functional-account --output-file <fifo>`` inside a disposable, real
functional-account container (``docker/entrypoint.sh``'s ``usermod`` rename establishes the
kernel-verified identity ``xx-user-init`` requires -- see docs/VAULT_SECURITY_DESIGN.md §3.3), then
feeds the resulting manifest into an operator-supplied provisioning command running on the host,
outside the container (e.g. ``docker secret create ... -``, which needs Docker/Swarm access a
plain container doesn't have).

The manifest is delivered over a bind-mounted named pipe, not a plain file: a regular file would
sit on host disk, readable by anything with matching permissions, for the whole window between the
container exiting and this wrapper deleting it. A FIFO never holds that content as stat-able file
content -- only as bytes in transit through a kernel pipe buffer between exactly this process and
the container. The reader thread attaches *before* the container starts, so it always wins the
rendezvous with the container's writer.

``docker run -it`` (not stdout piping) is used so the vault login/password ``getpass`` prompts
inside the container stay masked -- a pty is required for that, and once one exists, stdout and
stderr are merged at the kernel level before Docker can demultiplex them, which is why the
manifest can't travel over stdout at all here.

See ``docs/USER_ONBOARDING_AUTH.md`` for the full procedure.
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
        fifo_path = os.path.join(tmp_dir, 'manifest.fifo')
        os.mkfifo(fifo_path, 0o600)
        container_fifo_path = f'{_CONTAINER_MOUNT_DIR}/manifest.fifo'

        holder: dict = {}

        def _reader() -> None:
            try:
                with open(fifo_path) as f:  # blocking open is the point (see module docstring)
                    holder['payload'] = f.read()
            except OSError as ex:
                holder['error'] = ex

        # Started before `docker run` so this reader always wins the FIFO open() rendezvous --
        # see module docstring. Daemon: if the container never writes (e.g. it errors before
        # reaching that point), this thread stays blocked in open() forever, but a daemon thread
        # doesn't block process exit, so we simply abandon it rather than hang.
        reader_thread = threading.Thread(target=_reader, daemon=True)
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
        try:
            # No stdio overrides: inherits this process's own terminal, so the container's
            # getpass prompts are masked exactly as if a human ran `docker run -it` directly.
            result = subprocess.run(docker_argv, check=False)
            if result.returncode != 0:
                return RC(False, f'docker run failed with exit code {result.returncode}')

            reader_thread.join(timeout=10)
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
