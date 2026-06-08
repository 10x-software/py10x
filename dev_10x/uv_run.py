from __future__ import annotations

import sys
from pathlib import Path

from .uv_sync import read_persisted_profile, run_profile


def main():
    """`uv-run` companion to `uv-sync`: re-applies the source override of the profile
    last selected by `uv-sync` (read from .dev_10x_profile), plus the incremental build
    flags when XX_UV_INCREMENTAL is set, then runs `uv run <args>` and reverts the
    pyproject. This lets incremental runs work against local editable C++ packages
    without ever leaving pyproject.toml dirty.

    Usage: uv-run <command> [args...]   e.g.  uv-run pytest -q
    """
    project_root = Path('.').resolve()
    profile = read_persisted_profile(project_root)
    # seed=False: the venv was already prepared by `uv-sync`; `uv run` re-syncs anyway.
    run_profile(project_root, profile, 'run', sys.argv[1:], seed=False)


if __name__ == '__main__':
    main()
