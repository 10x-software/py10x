"""`python -m dev_10x.env_check [MODE] [--downstream]` - assert the venv holds what MODE should install.

Checks the *result* of an install, not how it was produced, so it guards uv-sync / xx-build against
uv quietly installing something else (e.g. the root's editable `[tool.uv.sources]` overriding an
install mode). Run from the repo root, in the venv under test.

For every first-party package it reads the PEP 610 `direct_url.json` (source tree, editable or not)
and, for the editable C++ packages, the arguments scikit-build-core baked into the generated
`_<name>_editable.py` loader (rebuild-on-import, verbose, build dir -> build type). Then it imports
the compiled modules, which also proves they load without a rebuild failing (e.g. `build/` gone).

MODE is an `./xx-build` build mode (dev, dev-release, ci-release) or one of uv-sync's
$XX_UV_INSTALL_MODE names, which map onto them. It defaults to $XX_UV_INSTALL_MODE, else the mode
`./xx-build set-mode` left in uv.toml (dev without one). `dev`'s build type is
$SKBUILD_CMAKE_BUILD_TYPE, else each package's `cmake.build-type`. `--downstream` also requires and
checks the downstreams (py10x-fin-base and its C++ members); without it they are ignored.
"""

from __future__ import annotations

import argparse
import ast
import importlib
import importlib.metadata as md
import json
import os
import sys
from pathlib import Path, PureWindowsPath
from urllib.parse import urlparse
from urllib.request import url2pathname

import tomllib

PROJECT_ROOT = Path.cwd()  # the py10x repo root (cwd)
CORE = 'py10x-core'
# Import name of each downstream C++ member (siblings import as their distribution name).
MEMBER_MODULES = {'py10x-fin-base-cxx': 'cxxfin'}

# What each build mode ([tool.dev_10x.modes] + the default `dev`) leaves behind for a local C++
# package. rebuild / verbose only apply to editable installs; None = not checked (build_type None:
# the package's own default, see _build_type).
MODES: dict[str, dict] = {
    'dev': {'editable': True, 'rebuild': True, 'verbose': False, 'build_type': None},
    'dev-release': {'editable': True, 'rebuild': True, 'verbose': False, 'build_type': 'Release'},
    'ci-release': {'editable': True, 'rebuild': False, 'verbose': None, 'build_type': 'Release'},
}
# uv-sync's XX_UV_INSTALL_MODE names -> the build mode uv-sync uses for them.
ALIASES = {'incremental_quiet': 'dev', 'incremental': 'dev', 'editable': 'ci-release', 'normal': 'ci-release'}


def _pyproject(path: Path) -> dict:
    return tomllib.loads((path / 'pyproject.toml').read_text(encoding='utf-8'))


def _workspace_members(src_dir: Path) -> dict[str, Path]:
    """`{dist-name: path}` for each `[tool.uv.workspace]` member under a packaging root."""
    pyproject = Path(src_dir) / 'pyproject.toml'
    if not pyproject.is_file():
        return {}
    out: dict[str, Path] = {}
    for pattern in _pyproject(Path(src_dir)).get('tool', {}).get('uv', {}).get('workspace', {}).get('members', []):
        for path in sorted(Path(src_dir).glob(pattern)):
            if (path / 'pyproject.toml').is_file() and (name := _pyproject(path).get('project', {}).get('name')):
                out[str(name)] = path.resolve()
    return out


def is_native(src_dir: Path) -> bool:
    """A C++ (scikit-build-core) package, as opposed to a pure-Python one."""
    pyproject = Path(src_dir) / 'pyproject.toml'
    return pyproject.is_file() and _pyproject(Path(src_dir)).get('build-system', {}).get('build-backend', '').startswith('scikit_build_core')


def native_members(src_dir: Path) -> dict[str, Path]:
    """`{dist-name: path}` for the C++ workspace members of a downstream (fin-base -> cxxfin)."""
    return {name: path for name, path in _workspace_members(src_dir).items() if is_native(path)}


def first_party(root: Path = PROJECT_ROOT) -> tuple[dict[str, Path], dict[str, Path], dict[str, Path]]:
    """(C++ siblings, downstreams, downstream C++ members) as {distribution name: source dir}."""
    cfg = _pyproject(root).get('tool', {}).get('dev_10x', {})
    siblings = {name: (root / spec['path']).resolve() for name, spec in cfg.get('siblings', {}).items()}
    downstreams = {name: (root / spec['path']).resolve() for name, spec in cfg.get('downstream', {}).items()}
    members = {name: path.resolve() for src in downstreams.values() for name, path in native_members(src).items()}
    return siblings, downstreams, members


def loader_settings(loader: Path) -> dict:
    """Arguments of the `install(...)` call at the end of a scikit-build-core editable loader."""
    for node in ast.walk(ast.parse(loader.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'install':
            args = [ast.literal_eval(a) for a in node.args]
            path = args[2] if len(args) > 2 else None
            return {
                'rebuild': bool(args[3]) if len(args) > 3 else False,
                'verbose': bool(args[4]) if len(args) > 4 else False,
                # build/py10x-build/<pkg>/<build type>/<wheel tag>
                'build_type': PureWindowsPath(path).parent.name if path else None,
                'build_dir': path,
            }
    raise ValueError(f'{loader}: no install(...) call found')


def installed(name: str) -> dict | None:
    """Installed state of one distribution, or None when it is not installed."""
    try:
        dist = md.distribution(name)
    except md.PackageNotFoundError:
        return None
    url = json.loads(dist.read_text('direct_url.json') or '{}')
    state = {
        'url': url.get('url'),
        'editable': bool(url.get('dir_info', {}).get('editable')),
        'local': 'dir_info' in url,
    }
    loader = Path(dist.locate_file(f'_{name.replace("-", "_")}_editable.py'))
    if loader.is_file():
        state.update(loader_settings(loader))
    return state


def _from_tree(state: dict, src: Path) -> bool:
    url = urlparse(state.get('url') or '')
    return url.scheme == 'file' and Path(url2pathname(url.path)).resolve() == src.resolve()


def _build_type(src: Path) -> str:
    return os.environ.get('SKBUILD_CMAKE_BUILD_TYPE') or _pyproject(src).get('tool', {}).get('scikit-build', {}).get('cmake', {}).get(
        'build-type', 'Release'
    )


def check_cxx(name: str, state: dict | None, src: Path, expect: dict) -> list[str]:
    if state is None:
        return [f'{name}: not installed']
    problems = []
    if not _from_tree(state, src):
        problems.append(f'{name}: expected an install from {src}, got {state.get("url") or "the index"}')
    if state['editable'] != expect['editable']:
        problems.append(
            f'{name}: expected {"editable" if expect["editable"] else "non-editable"}, got {"editable" if state["editable"] else "non-editable"}'
        )
    if state['editable'] and expect['editable']:
        for key in ('rebuild', 'verbose'):
            if expect[key] is not None and state.get(key) != expect[key]:
                problems.append(f'{name}: expected {key}={expect[key]}, got {state.get(key)}')
        build_type = expect.get('build_type') or _build_type(src)
        if state.get('build_type') and state['build_type'] != build_type:
            problems.append(f'{name}: expected build type {build_type}, got {state["build_type"]}')
    return problems


def check(mode: str, downstream: bool, root: Path = PROJECT_ROOT) -> tuple[list[str], list[str]]:
    """(problems, report lines) for the active venv."""
    expect = MODES[ALIASES.get(mode, mode)]
    siblings, downstreams, members = first_party(root)
    problems: list[str] = []
    report: list[str] = []

    def note(name: str, state: dict | None) -> None:
        if state is None:
            report.append(f'  {name}: not installed')
            return
        kind = 'editable' if state['editable'] else ('non-editable local' if state['local'] else 'index/other')
        extra = ''.join(f' {k}={state[k]}' for k in ('rebuild', 'verbose', 'build_type') if k in state)
        report.append(f'  {name}: {kind}{extra}')

    core = installed(CORE)
    note(CORE, core)
    if core is None or not core['editable'] or not _from_tree(core, root):
        problems.append(f'{CORE}: expected an editable install of {root}')
    for name, src in siblings.items():
        state = installed(name)
        note(name, state)
        problems += check_cxx(name, state, src, expect)
    if downstream:
        for name, src in downstreams.items():
            state = installed(name)
            note(name, state)
            if state is None or not state['editable'] or not _from_tree(state, src):
                problems.append(f'{name}: expected an editable install of {src}')
        for name, src in members.items():
            state = installed(name)
            note(name, state)
            problems += check_cxx(name, state, src, expect)
    return problems, report


def import_modules(downstream: bool, root: Path = PROJECT_ROOT) -> list[str]:
    """Import the compiled modules (in-place rebuild included, if the mode has one)."""
    siblings, _, members = first_party(root)
    # core_10x first, as real code does: it promotes py10x_kernel to RTLD_GLOBAL, which consumers like
    # cxxfin need on Linux (undefined BTraitable typeinfo otherwise).
    modules = ['core_10x', *(n.replace('-', '_') for n in siblings)]
    if downstream:
        modules += [MEMBER_MODULES.get(n, n.replace('-', '_')) for n in members]
    problems = []
    for module in modules:
        try:
            importlib.import_module(module)
        except Exception as exc:  # noqa: BLE001 - report every failing module, not just the first
            problems.append(f'import {module}: {type(exc).__name__}: {exc}')
    return problems


def default_mode(root: Path = PROJECT_ROOT) -> str:
    """$XX_UV_INSTALL_MODE (uv-sync), else the mode `./xx-build set-mode` left in uv.toml."""
    from dev_10x.xx_build import DEFAULT_MODE, active_mode

    return os.environ.get('XX_UV_INSTALL_MODE') or active_mode(root) or DEFAULT_MODE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='python -m dev_10x.env_check', description=__doc__.splitlines()[0])
    parser.add_argument('mode', nargs='?', default=default_mode(), choices=[*MODES, *ALIASES])
    parser.add_argument('--downstream', action='store_true', help='also require and check the downstreams (fin-base, cxxfin)')
    parser.add_argument('--no-import', action='store_true', help='skip importing the compiled modules')
    args = parser.parse_args(argv)

    problems, report = check(args.mode, args.downstream)
    if not args.no_import:
        problems += import_modules(args.downstream)
    print(f'env_check {args.mode}{" --downstream" if args.downstream else ""}:')
    print('\n'.join(report), flush=True)
    if problems:
        print('FAILED:\n' + '\n'.join(f'  - {p}' for p in problems), file=sys.stderr)
        return 1
    print('OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
