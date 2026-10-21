"""`xx-build` - set up (or start over) this checkout's development environment.

Usage, from the repo root (bash; Git Bash on Windows):

    ./xx-build init [uv sync args...]          # fresh clone
    ./xx-build init --clean [uv sync args...]  # delete .venv and build/, then the same

After that, plain `uv sync` / `uv run` keep the environment current. `init` exists because a fresh
environment needs an order uv cannot express on its own:

1. the C++ build toolchain (the `build` dependency group, versions from uv.lock) goes in first: the
   in-tree C++ packages build without isolation, and uv does not install a no-isolation package's
   toolchain before building it;
2. py10x-kernel / py10x-infra next: py10x-fin-base-cxx's build needs an installed, importable kernel
   (stub generation on every OS, kernel's import library on Windows);
3. then everything else (default dependency groups), py10x-fin-base-cxx included.

The C++ packages are always force-rebuilt (`--reinstall-package`): uv's cache may still hold wheels
that point at a deleted build/ dir. Extra arguments (e.g. `--locked`, `--config-file FILE`,
`--no-group test`) are passed to the `uv sync` calls of steps 2 and 3.

`init` refuses to run when .venv or build/ already exists, so it never silently rebuilds over an
existing environment; `--clean` deletes both first.

Standard library only: it runs before the venv exists, via `./xx-build` ->
`uv run --no-project --isolated -m dev_10x.xx_build`. uv is invoked as `$UV` (set by `uv run`), so a
venv-installed uv never replaces the uv that started it.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
KERNEL_PACKAGES = ('py10x-kernel', 'py10x-infra')
DOWNSTREAM_CXX_PACKAGES = ('py10x-fin-base-cxx',)
USAGE = 'Usage: ./xx-build init [--clean] [uv sync args...]'


def _uv() -> str:
    return os.environ.get('UV') or 'uv'


def _reinstall(names: tuple[str, ...]) -> list[str]:
    return [arg for name in names for arg in ('--reinstall-package', name)]


def _rmtree(path: Path) -> None:
    """`shutil.rmtree` that also removes read-only files: on Windows it cannot delete the read-only git
    pack files CMake FetchContent leaves under build/.../_deps/*/.git."""

    def make_writable_and_retry(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=make_writable_and_retry)
    else:
        shutil.rmtree(path, onerror=make_writable_and_retry)


def _uv_env() -> dict[str, str]:
    """The environment for the inner uv calls, minus the VIRTUAL_ENV of `./xx-build`'s own isolated
    `uv run` environment (uv would warn on every call that it does not match the project's .venv)."""
    return {k: v for k, v in os.environ.items() if k != 'VIRTUAL_ENV'}


def init_commands(sync_args: list[str]) -> list[list[str]]:
    """The uv calls `init` runs, in order."""
    uv = _uv()
    return [
        [uv, 'venv'],
        [uv, 'sync', '--frozen', '--only-group', 'build'],
        [uv, 'sync', '--no-default-groups', '--group', 'build', *_reinstall(KERNEL_PACKAGES), *sync_args],
        [uv, 'sync', *_reinstall(DOWNSTREAM_CXX_PACKAGES), *sync_args],
    ]


def init(clean: bool, sync_args: list[str], root: Path = ROOT) -> int:
    existing = [p for p in (root / '.venv', root / 'build') if p.exists()]
    if existing and not clean:
        names = ' and '.join(p.name + '/' for p in existing)
        print(f'xx-build init: {names} already exist - run `./xx-build init --clean` to delete them and start over.', file=sys.stderr)
        return 1
    for path in existing:
        print(f'xx-build init: removing {path.name}/', flush=True)
        _rmtree(path)
    env = _uv_env()
    for cmd in init_commands(sync_args):
        print('$', ' '.join(cmd), flush=True)
        result = subprocess.run(cmd, cwd=root, env=env, check=False)
        if result.returncode:
            return result.returncode
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return 0 if args else 2
    if args[0] != 'init':
        print(USAGE, file=sys.stderr)
        return 2
    rest = args[1:]
    clean = '--clean' in rest
    return init(clean, [a for a in rest if a != '--clean'])


if __name__ == '__main__':
    sys.exit(main())
