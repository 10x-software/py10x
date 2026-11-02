"""`uv-sync` - retired: prints what replaces it and fails, so old habits and scripts notice."""

from __future__ import annotations

import sys

MESSAGE = """\
uv-sync is retired. From the py10x repo root:
  ./xx-build init                  first setup, or `init --clean` to start over (dev mode)
  uv sync                          re-sync after a pull or a pyproject change
  ./xx-build set-mode <mode>       switch build mode: dev | dev-release | ci-release
  ./xx-build rebuild               rebuild the C++ packages in order, in the active mode
  ./xx-build show-mode             the current build mode
  uv run <command>                 run in the venv (replaces uv-run)
Leave out fin-base with `--no-group test --no-group test-extras`, core's extras with `--no-group extras`.
See CONTRIBUTING.md#development-setup."""


def main(argv: list[str] | None = None) -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main())
