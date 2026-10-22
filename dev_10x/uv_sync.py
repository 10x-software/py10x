"""`uv-sync py10x-dev [--all-extras] [--with-downstream] [uv sync args...]` - thin wrapper over `./xx-build`.

Kept for CI and existing habits; new setups use `./xx-build` and plain `uv sync` (see dev_10x/xx_build.py).
$XX_UV_INSTALL_MODE picks the build mode:

    incremental_quiet (default), incremental  ->  dev         (Debug, rebuild-on-import)
    editable, normal                          ->  ci-release  (Release, no rebuild on import)

and the arguments pick the dependency groups of the plain `uv sync` the env otherwise gets:

    --all-extras        keep the `extras` group (core's optional extras); without it: --no-group extras
    --with-downstream   keep the fin-base groups `test` / `test-extras`; without it they are left out,
                        so xxfin is not importable (core isolation). Names after it are ignored.

Then it runs `./xx-build set-mode <mode>` (or `init --mode <mode>` without a .venv): uv.toml for the
mode plus the ordered sync, other arguments passed on to `uv sync`. `--upgrade` is dropped - uv.lock
changes only through `xx-constraints compile`. The `user` / `domain-dev` profiles are gone: a domain
repo syncs against py10x with its own `uv sync`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path.cwd()  # the py10x repo root (cwd)
PROFILES = ('py10x-dev', 'py10x-core-dev')  # py10x-core-dev: legacy alias
MODES = {'incremental_quiet': 'dev', 'incremental': 'dev', 'editable': 'ci-release', 'normal': 'ci-release'}
XX_BUILD = ['uv', 'run', '--no-project', '--isolated', '--with', 'tomlkit', '-m', 'dev_10x.xx_build']  # = ./xx-build
USAGE = 'Usage: uv-sync py10x-dev [--all-extras] [--with-downstream] [uv sync args...]'


def _parse_with_downstream(uv_args: tuple[str, ...]) -> tuple[bool, set[str] | None, list[str]]:
    """Strip `--with-downstream [name…]` from uv_args. Returns (enabled, name filter or None, rest)."""
    enabled = False
    names: list[str] = []
    rest: list[str] = []
    i = 0
    args = list(uv_args)
    while i < len(args):
        if args[i] == '--with-downstream':
            enabled = True
            i += 1
            while i < len(args) and not args[i].startswith('-'):
                names.append(args[i])
                i += 1
            continue
        rest.append(args[i])
        i += 1
    return enabled, (set(names) if names else None), rest


def build_mode() -> str:
    raw = os.environ.get('XX_UV_INSTALL_MODE', 'incremental_quiet').strip()
    if raw not in MODES:
        raise ValueError(f'XX_UV_INSTALL_MODE must be one of {tuple(MODES)}, got {raw!r}')
    return MODES[raw]


def xx_build_command(uv_args: tuple[str, ...], root: Path = PROJECT_ROOT) -> list[str]:
    """The `./xx-build` call `uv-sync py10x-dev <uv_args>` makes."""
    with_downstream, _, rest = _parse_with_downstream(uv_args)
    sync_args = [a for a in rest if a != '--all-extras' and a != '--upgrade']
    if '--all-extras' not in rest:
        sync_args = ['--no-group', 'extras', *sync_args]
    if not with_downstream:
        sync_args = ['--no-group', 'test', '--no-group', 'test-extras', *sync_args]
    mode = build_mode()
    if (root / '.venv').exists():
        return [*XX_BUILD, 'set-mode', mode, *sync_args]
    return [*XX_BUILD, 'init', '--mode', mode, *sync_args]


def ensure_chromium_installed() -> None:
    try:
        import playwright  # imported only to check the package exists
    except ImportError:
        return
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            p.chromium.launch(headless=True)
        return
    except PlaywrightError:
        print('Installing Playwright Chromium...')
        subprocess.run(['playwright', 'install', 'chromium'], check=True)
        print('Done.')


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in PROFILES:
        print(USAGE, file=sys.stderr)
        if args and args[0] in ('user', 'domain-dev'):
            print(f'uv-sync: the `{args[0]}` profile is gone - a domain repo syncs against py10x with its own `uv sync`.', file=sys.stderr)
        return 2
    if '--upgrade' in args:
        print('uv-sync: ignoring --upgrade (uv.lock changes only through `xx-constraints compile`).', file=sys.stderr)
    try:
        cmd = xx_build_command(tuple(args[1:]))
    except ValueError as exc:
        print(f'uv-sync: {exc}', file=sys.stderr)
        return 2
    print('$', ' '.join(cmd), flush=True)
    rc = subprocess.run(cmd, cwd=PROJECT_ROOT, check=False).returncode
    if rc == 0:
        ensure_chromium_installed()
    return rc


if __name__ == '__main__':
    sys.exit(main())
