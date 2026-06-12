from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main():
    """`uv-run` companion to `uv-sync`: run a command in the already-prepared venv WITHOUT letting
    `uv run` re-sync (which would reconcile the env back to `pyproject.toml` and undo the source
    overlay that `uv-sync` installed). The redesigned `uv-sync` no longer edits `pyproject.toml`,
    so there is nothing to re-apply here - just pass through to `uv run --no-sync`.

    Usage: uv-run <command> [args...]   e.g.  uv-run pytest -q
    """
    subprocess.run(['uv', 'run', '--no-sync', *sys.argv[1:]],
                   cwd=Path('.').resolve(), check=True)


if __name__ == '__main__':
    main()
