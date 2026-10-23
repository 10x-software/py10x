#!/usr/bin/env python3
"""Prove the provisioning FIFO handoff against a built functional-account image.

The host opens the read end and drops the read bit. The container entrypoint chowns
only the ``--output-file`` path, then uid 10001 writes it and cannot open it for
reading. A second FIFO in the same directory stays owned by the host user.

Called from ``.github/workflows/ci.yml`` after ``py10x-functional-e2e`` is loaded.
Not a pytest: it needs Docker and that image.

Usage: python3 docker/fifo_handoff_e2e.py IMAGE
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

_MOUNT = '/var/run/xx-provisioning-output'
_ACCOUNT = 'xx-e2e-ci'
_PAYLOAD = b'e2e-fifo'
_CONTAINER = """
import os, sys
path = sys.argv[sys.argv.index("--output-file") + 1]
try:
    os.open(path, os.O_RDONLY | os.O_NONBLOCK)
except PermissionError:
    pass
else:
    raise SystemExit("container uid opened the fifo for reading")
fd = os.open(path, os.O_WRONLY)
os.write(fd, b"e2e-fifo")
os.close(fd)
"""


def main(image: str) -> None:
    tmp = tempfile.mkdtemp()
    read_fd: int | None = None
    try:
        os.chmod(tmp, 0o700)
        fifo_path = os.path.join(tmp, f'{_ACCOUNT}.fifo')
        other_path = os.path.join(tmp, 'other.fifo')
        os.mkfifo(fifo_path, 0o400)
        os.chmod(fifo_path, 0o400)
        read_fd = os.open(fifo_path, os.O_RDONLY | os.O_NONBLOCK)
        os.chmod(fifo_path, 0o200)
        os.chmod(tmp, 0o711)
        os.mkfifo(other_path, 0o600)
        host_uid = os.getuid()

        container_fifo = f'{_MOUNT}/{_ACCOUNT}.fifo'
        result = subprocess.run(
            [
                'docker',
                'run',
                '--rm',
                '-e',
                f'FUNCTIONAL_ACCOUNT_ID={_ACCOUNT}',
                '-v',
                f'{tmp}:{_MOUNT}',
                image,
                'python',
                '-c',
                _CONTAINER,
                '--output-file',
                container_fifo,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise SystemExit(f'docker run failed ({result.returncode})\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}')

        chunks: list[bytes] = []
        while True:
            try:
                chunk = os.read(read_fd, 65536)
            except BlockingIOError:
                break
            if not chunk:
                break
            chunks.append(chunk)
        payload = b''.join(chunks)
        if payload != _PAYLOAD:
            raise SystemExit(f'host read {payload!r}, expected {_PAYLOAD!r}')
        if os.stat(fifo_path).st_uid != 10001:
            raise SystemExit(f'provisioning fifo uid is {os.stat(fifo_path).st_uid}, expected 10001')
        if os.stat(other_path).st_uid != host_uid:
            raise SystemExit(f'other fifo uid changed to {os.stat(other_path).st_uid}')
    finally:
        if read_fd is not None:
            os.close(read_fd)
        for name in os.listdir(tmp):
            try:
                os.remove(os.path.join(tmp, name))
            except OSError:
                pass
        os.rmdir(tmp)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: python3 docker/fifo_handoff_e2e.py IMAGE')
    main(sys.argv[1])
