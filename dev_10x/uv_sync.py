"""`uv-sync <profile>` - prepare the venv for a chosen dependency-source profile.

Redesign (see `dev_10x/README.md`): instead of transiently rewriting `pyproject.toml`
`[tool.uv.sources]` and running `uv sync`, we drive `uv pip install` directly. Nothing edits
pyproject, so the tree stays clean and setuptools-scm never stamps a dirty guess-next-dev version -
which means py10x-core (and the slow `playwright install` build hook) is only rebuilt when its
source version actually changes.

Per package the desired *source* comes from the profile:
  - local : editable install from the sibling's local dir (`[tool.dev_10x.siblings]` path, or `.`)
  - git   : `pkg @ git+<remote>@<branch>[#subdirectory=...]`, URL derived from `origin`
  - index : released wheel from the package index

Install order (so already-correct local/git siblings are kept, not re-pulled):
  1. siblings (local/git) - install only if the reinstall rules say so;
  2. `uv pip install --all-extras --requirements pyproject.toml` - core's deps+extras, additive;
  3. py10x-core itself (local/git) - install only if needed.

Reinstall rules (per package): (a) not installed; (b) installed from a different source;
(c) local source and installed version != setuptools-scm of the source; (d) git -> always.
Source is classified from PEP 610 `direct_url.json`: absent -> index; `dir_info.editable` -> local;
otherwise -> git/other.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

    from dev_10x.xx_helpers import InstalledSourceHelpers

PROJECT_ROOT = Path('.').resolve()  # the py10x repo root (cwd)
PROFILE_FILE = '.dev_10x_profile'
CORE = 'py10x-core'
PROFILES = ('user', 'domain-dev', 'py10x-dev', 'py10x-core-dev')
CXX_BUILD_TOOLCHAIN = ['scikit-build-core', 'setuptools-scm', 'cmake', 'ninja', 'editables']
# Mandatory third-party freeze, applied to every `uv pip install` (see dev_10x/constraints.py).
# constraints.txt excludes the three first-party packages, so it never fights the sibling/core
# editable/git installs - only their third-party transitives are pinned.
CONSTRAINTS = ('-c', 'constraints.txt')


# --------------------------------------------------------------------------------------------
# venv + runtime deps
# --------------------------------------------------------------------------------------------
def ensure_env_and_runtime_deps(project_root: Path) -> ModuleType:
    if not (project_root / '.venv' / 'pyvenv.cfg').is_file():
        subprocess.run(['uv', 'venv'], cwd=project_root, check=True)
    try:
        import packaging  # noqa: F401 - xx_helpers import gate
        import tomlkit
        import setuptools_scm  # imported only to check availability
    except ImportError:
        subprocess.run(['uv', 'pip', 'install', '--python', sys.executable, '--quiet',
                        '-c', 'constraints.txt', 'packaging', 'tomlkit', 'setuptools-scm'],
                       cwd=project_root, check=True)
        import tomlkit
    return tomlkit


def _installed_source_helpers(project_root: Path) -> InstalledSourceHelpers:
    """Lazy import: `xx_helpers` needs bootstrap deps installed first."""
    from dev_10x.xx_helpers import InstalledSourceHelpers

    return InstalledSourceHelpers(project_root)


# --------------------------------------------------------------------------------------------
# config: [tool.dev_10x] siblings + branch, with git URLs derived from `origin`
# --------------------------------------------------------------------------------------------
def _dev10x_cfg(tomlkit) -> dict:
    doc = tomlkit.parse((PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    return doc.get('tool', {}).get('dev_10x', {})


def _git_remote() -> str:
    return subprocess.check_output(
        ['git', 'remote', 'get-url', 'origin'], cwd=PROJECT_ROOT, text=True).strip()


def _swap_repo(remote: str, repo_dir: str) -> str:
    """`…/py10x.git` -> `…/{repo_dir}.git`, preserving the SSH-vs-HTTPS form of `remote`."""
    base, _self = remote.rsplit('/', 1)
    return f'{base}/{repo_dir}.git'


def _normalize_git_url(url: str) -> str:
    """Convert SCP-style SSH remote to ssh:// form required by `uv pip`.

    `git@host:org/repo.git`  ->  `ssh://git@host/org/repo.git`

    `uv pip install 'pkg @ git+<url>@branch'` only accepts RFC-3986 URLs; bare
    SCP remotes (no scheme) are not valid there even though git itself accepts them.
    HTTPS remotes are returned unchanged.
    """
    if '://' not in url and ':' in url:
        userhost, path = url.split(':', 1)
        return f'ssh://{userhost}/{path}'
    return url


def packages(tomlkit) -> dict[str, dict]:
    """Per-package source descriptor: {'local': Path, 'git': url, 'subdir': str|None, 'cxx': bool}.

    py10x-core is the current repo (`.`); siblings come from `[tool.dev_10x.siblings]`, where a
    path like `../cxx10x/core_10x` yields repo dir `cxx10x` (the sibling's git repo, same remote
    host/org) and subdirectory `core_10x`.
    """
    remote = _git_remote()
    pkgs: dict[str, dict] = {
        CORE: {'local': PROJECT_ROOT, 'git': remote, 'subdir': None, 'cxx': False},
    }
    for name, spec in _dev10x_cfg(tomlkit).get('siblings', {}).items():
        rel = PurePosixPath(spec['path'])
        non_dotdot = [p for p in rel.parts if p != '..']
        repo_dir = non_dotdot[0]
        subdir = '/'.join(non_dotdot[1:]) or None
        pkgs[name] = {
            'local': (PROJECT_ROOT / spec['path']).resolve(),
            'git': spec.get('git') or _swap_repo(remote, repo_dir),
            'subdir': spec.get('subdirectory', subdir),
            'cxx': True,  # siblings are the compiled C++ packages
        }
    return pkgs


def profile_kinds(profile: str, pkg_names: list[str]) -> dict[str, str]:
    """Desired source kind ('local'|'git'|'index') per package for `profile`."""
    siblings = [p for p in pkg_names if p != CORE]
    if profile == 'user':
        return {CORE: 'local', **{s: 'index' for s in siblings}}
    if profile == 'domain-dev':
        return {p: 'git' for p in pkg_names}
    if profile == 'py10x-dev':
        return {CORE: 'local', **{s: 'git' for s in siblings}}
    if profile == 'py10x-core-dev':
        return {p: 'local' for p in pkg_names}
    raise ValueError(f'unknown profile {profile!r}')


# --------------------------------------------------------------------------------------------
# installed-source detection (PEP 610) + reinstall decision
# --------------------------------------------------------------------------------------------
def source_version(src: Path) -> str:
    # stderr suppressed: hatch-vcs projects have no [tool.setuptools_scm] section, so the scm CLI
    # logs a harmless "toml section missing" warning while still computing the git version.
    return subprocess.check_output(
        [sys.executable, '-m', 'setuptools_scm'], cwd=src, text=True,
        stderr=subprocess.DEVNULL).strip()


def _sibling_pin(name: str) -> str | None:
    """Forward pin specifier for sibling `name` from core's pyproject, or None when absent."""
    from dev_10x.xx_helpers import PyProjectHelpers

    try:
        return PyProjectHelpers.dependency_spec(PROJECT_ROOT / 'pyproject.toml', name)
    except KeyError:
        return None


def need_install(name: str, kind: str, pkg: dict, *, verbose: bool = True,
                 installs: InstalledSourceHelpers | None = None) -> bool:
    installs = installs or _installed_source_helpers(PROJECT_ROOT)
    cur_kind, cur_path = installs.installed_source(name)
    reason = None
    if cur_kind is None:
        reason = 'not installed'
    elif kind == 'git':
        reason = 'git source (always reinstall)'
    elif kind == 'index':
        if cur_kind != 'index':
            reason = f'switching {cur_kind} -> index'
    elif kind == 'local':
        if cur_kind != 'local':
            reason = f'switching {cur_kind} -> local editable'
        elif cur_path is not None and cur_path.resolve() != pkg['local'].resolve():
            reason = f'editable path changed -> {pkg["local"]}'
        else:
            try:
                installed, src = installs.installed_version(name), source_version(pkg['local'])
                if installed != src:
                    reason = f'version drift {installed} -> {src}'
            except Exception as e:  # be safe: any failure -> reinstall
                reason = f'version check failed ({e})'
    if verbose:
        print(f'  {name}: {"reinstall - " + reason if reason else "up to date, skipping"}')
    return reason is not None


# --------------------------------------------------------------------------------------------
# install actions
# --------------------------------------------------------------------------------------------
def _run(args: list[str]) -> None:
    print('  $', ' '.join(args))
    subprocess.run(args, cwd=PROJECT_ROOT, check=True)


def _pip_install(*args: str) -> None:
    """`uv pip install` with the mandatory constraints freeze applied."""
    _run(['uv', 'pip', 'install', *args, *CONSTRAINTS])


def _windows_cxx_cmake_flags(name: str) -> list[str]:
    """MSVC toolset pin for py10x-kernel/infra (matches cxx10x cibuildwheel wheel builds)."""
    if sys.platform != 'win32':
        return []
    return [
        '--config-settings-package', f'{name}:cmake.args=-T',
        '--config-settings-package', f'{name}:cmake.args=v143,version=14.44',
    ]


def _incremental_flags(name: str, src_dir: Path, venv: Path) -> list[str]:
    """No-isolation incremental rebuild flags for a local C++ package (XX_UV_INCREMENTAL).
    Build type comes from XX_UV_BUILD_TYPE (default Release); each type gets its own build
    dir so switching Debug<->Release does not force a full reconfigure/rebuild."""
    build_type = os.getenv('XX_UV_BUILD_TYPE', 'Release')
    build_dir = f"{(venv / 'py10x-build' / name / build_type).as_posix()}/{{wheel_tag}}"
    verbose = int(os.getenv('XX_UV_INCREMENTAL',0))==1
    return [
        '--no-build-isolation-package',
        name,
        '--config-settings-package',
        f'{name}:build-dir={build_dir}',
        '--config-settings-package',
        f'{name}:cmake.build-type={build_type}',
        '--config-settings-package',
        f'{name}:editable.rebuild=true',
        '--config-settings-package',
        f'{name}:editable.verbose={str(bool(verbose)).lower()}',
    ]


def install_local(name: str, pkg: dict, pin: str | None, incremental: int, verbose: bool) -> None:
    args = ['-e', str(pkg['local'])]
    if pin:
        args.append(f'{name} ({pin})')
    args.append(f'--reinstall-package={name}')
    if pkg['cxx']:
        args += _windows_cxx_cmake_flags(name)
    if incremental and pkg['cxx']:
        args += _incremental_flags(name, pkg['local'], PROJECT_ROOT / '.venv')
    if verbose:
        args.append('--verbose')
    _pip_install(*args)


def install_git(name: str, pkg: dict, branch: str) -> None:
    git_url = _normalize_git_url(pkg['git'])
    spec = f'{name} @ git+{git_url}@{branch}'
    if pkg['subdir']:
        spec += f'#subdirectory={pkg["subdir"]}'
    args = [spec, f'--reinstall-package={name}']
    if pkg['cxx']:
        args += _windows_cxx_cmake_flags(name)
    _pip_install(*args)


# --------------------------------------------------------------------------------------------
# the sync
# --------------------------------------------------------------------------------------------
def _maybe_wait_for_sibling_branch() -> None:
    """Optional pre-sync poll (CI main-push race). See `dev_10x/README.md` CI gotchas."""
    branch = os.environ.get('WAIT_FOR_SIBLING_BRANCH', '').strip()
    if not branch:
        return
    from dev_10x import xx_ci

    sync_base = os.environ.get('WAIT_FOR_SIBLING_BRANCH_SYNC_BASE', '').strip() == '1'
    timeout = os.environ.get('WAIT_FOR_SIBLING_BRANCH_TIMEOUT', '120')
    interval = os.environ.get('WAIT_FOR_SIBLING_BRANCH_INTERVAL', '5')
    refresh = ' (refreshing py10x each attempt)' if sync_base else ''
    print(
        f'uv-sync: waiting for coordinated sibling pins on branch {branch!r}{refresh} '
        f'(timeout={timeout}s, interval={interval}s)...'
    )
    code = xx_ci.wait_sibling_branch_ready(
        PROJECT_ROOT, branch, sync_base=sync_base, verbose=True)
    if code:
        raise SystemExit(code)
    print(f'uv-sync: sibling pins ready on branch {branch!r}')


def uv_sync(profile: str, *uv_args: str) -> None:
    tomlkit = ensure_env_and_runtime_deps(PROJECT_ROOT)
    _maybe_wait_for_sibling_branch()
    pkgs = packages(tomlkit)
    branch = _dev10x_cfg(tomlkit).get('branch', 'main')
    kinds = profile_kinds(profile, list(pkgs))
    siblings = [p for p in pkgs if p != CORE]
    incremental = int(os.environ.get('XX_UV_INCREMENTAL', 0))
    prev_incremental = read_incremental_state(PROJECT_ROOT)
    toggled = prev_incremental is not None and prev_incremental != incremental

    installs = _installed_source_helpers(PROJECT_ROOT)

    print(f'uv-sync `{profile}`: ' + ', '.join(f'{p}={kinds[p]}' for p in pkgs))
    if toggled:
        print(f'XX_UV_INCREMENTAL toggled ({prev_incremental} -> {incremental}): '
              f'forcing rebuild of local C++ packages.')

    if incremental and any(kinds[s] == 'local' and pkgs[s]['cxx'] for s in siblings):
        print('XX_UV_INCREMENTAL set: no-build-isolation incremental rebuilds for local C++ packages.')
        # Seed the toolchain so the cold metadata hook + import-time `cmake --build` have it.
        _pip_install('--quiet', *CXX_BUILD_TOOLCHAIN)
    verbose = '--verbose' in uv_args
    # 1. siblings (local/git). Index siblings are handled by step 2; force a swap there only if the
    #    sibling is currently installed from a non-index source.
    print('1. siblings:')
    index_swaps: list[str] = []
    for s in siblings:
        kind = kinds[s]
        if kind == 'index':
            if installs.installed_source(s)[0] not in (None, 'index'):
                index_swaps.append(s)
            print(f'  {s}: index (resolved with core deps in step 2'
                  f'{" - forcing swap" if s in index_swaps else ""})')
            continue
        do = need_install(s, kind, pkgs[s], installs=installs)
        if not do and toggled and kind == 'local' and pkgs[s]['cxx']:
            print(f'  {s}: reinstall - build mode changed (XX_UV_INCREMENTAL)')
            do = True
        if do:
            if kind == 'local':
                install_local(s, pkgs[s], pin=_sibling_pin(s),
                              incremental=incremental, verbose=verbose)
            else:  # git
                install_git(s, pkgs[s], branch)

    # 2. core's deps (additive: keeps the local/git siblings from step 1; pulls/refreshes index
    #    siblings). Extras are NOT forced - pass `--all-extras` / `--extra X` as uv-sync args; the
    #    `uv pip` interface binds them to this `--requirements` source.
    print('2. core deps:')
    reinstall = [f'--reinstall-package={s}' for s in index_swaps]
    _pip_install('--requirements', 'pyproject.toml', *reinstall, *uv_args)

    # 3. py10x-core itself.
    print('3. py10x-core:')
    ck = kinds[CORE]
    if ck == 'git':
        install_git(CORE, pkgs[CORE], branch)
    elif need_install(CORE, 'local', pkgs[CORE], installs=installs):
        install_local(CORE, pkgs[CORE], pin=None, incremental=False, verbose=verbose)  # pure Python

    # Guard: a local sibling that came back non-editable means a pin pulled an index/other build.
    for s in siblings:
        if kinds[s] == 'local' and installs.installed_source(s)[0] != 'local':
            raise RuntimeError(
                f'{s}: expected an editable local install but it is '
                f'{installs.installed_source(s)[0]!r} - py10x-core\'s pin likely pulled a non-editable build')

    persist_profile(PROJECT_ROOT, profile)
    persist_incremental_state(PROJECT_ROOT, incremental)
    print(f'uv-sync `{profile}` done.')


# --------------------------------------------------------------------------------------------
# profile persistence (informational; uv-run no longer needs it)
# --------------------------------------------------------------------------------------------
def persist_profile(project_root: Path, profile: str) -> None:
    (project_root / PROFILE_FILE).write_text(profile + '\n', encoding='utf-8')


def read_persisted_profile(project_root: Path) -> str:
    f = project_root / PROFILE_FILE
    return f.read_text().strip() if f.is_file() else ''


def _incremental_marker(project_root: Path) -> Path:
    # In .venv so it tracks the build mode of the *currently installed* editable C++ packages and
    # resets whenever the venv is recreated.
    return project_root / '.venv' / '.xx_uv_incremental'


def read_incremental_state(project_root: Path) -> int | None:
    f = _incremental_marker(project_root)
    return int(f.read_text().strip()) if f.is_file() else None


def persist_incremental_state(project_root: Path, incremental: int) -> None:
    _incremental_marker(project_root).write_text(str(incremental))


def ensure_chromium_installed() -> None:
    try:
        import playwright  # imported only to check the package exists
    except ImportError:
        return
    from playwright.sync_api import Error as PlaywrightError, sync_playwright
    try:
        with sync_playwright() as p:
            p.chromium.launch(headless=True)
        return
    except PlaywrightError:
        print('Installing Playwright Chromium...')
        subprocess.run(['playwright', 'install', 'chromium'], check=True)
        print('Done.')


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in PROFILES:
        print(f'Usage: uv-sync {"|".join(PROFILES)} [extra `uv pip install` options]')
        return
    profile = sys.argv[1]
    uv_sync(profile, *sys.argv[2:])
    if profile == 'py10x-core-dev':
        ensure_chromium_installed()


if __name__ == '__main__':
    main()
