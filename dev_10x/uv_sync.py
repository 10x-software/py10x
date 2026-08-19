"""`uv-sync <profile>` - prepare the venv for a chosen dependency-source profile.

Redesign (see `dev_10x/README.md`): instead of transiently rewriting `pyproject.toml`
`[tool.uv.sources]` and running `uv sync`, we drive `uv pip install` directly. Nothing edits
pyproject, so the tree stays clean and setuptools-scm never stamps a dirty guess-next-dev version -
which means py10x-core (and the slow `playwright install` build hook) is only rebuilt when its
source version actually changes.

Per package the desired *source* comes from the profile:
  - local : install from the sibling's local dir (`[tool.dev_10x.siblings]` path, or `.`) - editable
    unless XX_UV_INSTALL_MODE=normal for that package (see INSTALL_MODES below)
  - git   : `pkg @ git+<remote>@<branch>[#subdirectory=...]`, URL derived from `origin`
  - index : released wheel from the package index

Install order (so already-correct local/git siblings are kept, not re-pulled):
  1. siblings / opt-in downstreams (local/git) - install only if the reinstall rules say so;
     `--all-extras` / `--extra` are forwarded onto downstream package installs;
  2. `uv pip install --all-extras --requirements pyproject.toml` - core's deps+extras, additive;
  3. py10x-core itself (local/git) - install only if needed.

Reinstall rules (per package): (a) not installed; (b) installed from a different source;
(c) local source and installed version != setuptools-scm of the source; (d) git -> always.
Source is classified from PEP 610 `direct_url.json`: absent -> index; `dir_info.editable` -> local;
otherwise -> git/other. A consequence: XX_UV_INSTALL_MODE=normal siblings are never classified
'local' (they're not editable), so they reinstall on every invocation - a non-issue for a
build-once CI/image run (the intended use), a minor cost for repeated local invocations.
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

PROJECT_ROOT = Path.cwd()  # the py10x repo root (cwd)
PROFILE_FILE = '.dev_10x_profile'
CORE = 'py10x-core'
PROFILES = ('user', 'domain-dev', 'py10x-dev', 'py10x-core-dev')
CXX_BUILD_TOOLCHAIN = ['scikit-build-core', 'setuptools-scm', 'cmake', 'ninja', 'editables']

# XX_UV_INSTALL_MODE controls how local C++ siblings (py10x-kernel/py10x-infra) get installed:
#   normal            plain, non-editable build+install - no ongoing dependency on the sibling's
#                      source tree or a persistent build-dir; right for a build-once image/CI run.
#   editable          (default) editable, isolated build each invocation - slower per-install but
#                      hermetic; matches every existing behavior when the var is left unset.
#   incremental       editable + no-build-isolation + a persistent build-dir + rebuild-on-*import*
#                      (not just at install time) - for iterating on C++ source locally.
#   incremental_quiet same as incremental, with scikit-build-core's per-import rebuild-check log
#                      spam silenced (editable.verbose=false).
# py10x-core itself always installs editable regardless of this setting (see uv_sync(), step 3) -
# core is pure Python, and a non-editable copy in site-packages would create a second, conflicting
# copy of the package for tests collected by path from the source tree to import against.
INSTALL_MODES = ('normal', 'editable', 'incremental', 'incremental_quiet')
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
        import packaging
        import setuptools_scm  # imported only to check availability
        import tomlkit
    except ImportError:
        subprocess.run(
            ['uv', 'pip', 'install', '--python', sys.executable, '--quiet', '-c', 'constraints.txt', 'packaging', 'tomlkit', 'setuptools-scm'],
            cwd=project_root,
            check=True,
        )
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
    return subprocess.check_output(['git', 'remote', 'get-url', 'origin'], cwd=PROJECT_ROOT, text=True).strip()


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
    """Per-package source descriptor: local/git/subdir/cxx/downstream.

    py10x-core is the current repo (`.`); siblings come from `[tool.dev_10x.siblings]` (`cxx=True`);
    optional downstreams from `[tool.dev_10x.downstream]` (`cxx=False`, omitted from default sync).
    """
    remote = _git_remote()
    pkgs: dict[str, dict] = {
        CORE: {'local': PROJECT_ROOT, 'git': remote, 'subdir': None, 'cxx': False, 'downstream': False},
    }
    cfg = _dev10x_cfg(tomlkit)
    for name, spec in cfg.get('siblings', {}).items():
        rel = PurePosixPath(spec['path'])
        non_dotdot = [p for p in rel.parts if p != '..']
        repo_dir = non_dotdot[0]
        subdir = '/'.join(non_dotdot[1:]) or None
        pkgs[name] = {
            'local': (PROJECT_ROOT / spec['path']).resolve(),
            'git': spec.get('git') or _swap_repo(remote, repo_dir),
            'subdir': spec.get('subdirectory', subdir),
            'cxx': True,  # siblings are the compiled C++ packages
            'downstream': False,
        }
    for name, spec in cfg.get('downstream', {}).items():
        rel = PurePosixPath(spec['path'])
        if '..' in rel.parts:
            non_dotdot = [p for p in rel.parts if p != '..']
            git_url = _swap_repo(remote, non_dotdot[0])
            subdir = '/'.join(non_dotdot[1:]) or None
        else:
            # Same-repo nested path (e.g. xx_fin): this repo's remote + subdirectory.
            git_url = remote
            subdir = None if rel.parts in ((), ('.',)) else str(rel)
        pkgs[name] = {
            'local': (PROJECT_ROOT / spec['path']).resolve(),
            'git': spec.get('git') or git_url,
            'subdir': spec.get('subdirectory', subdir),
            'cxx': False,
            'downstream': True,
        }
    return pkgs


def profile_kinds(profile: str, pkg_names: list[str]) -> dict[str, str]:
    """Desired source kind ('local'|'git'|'index') per package for `profile`."""
    others = [p for p in pkg_names if p != CORE]
    if profile == 'user':
        return {CORE: 'local', **{s: 'index' for s in others}}
    if profile == 'domain-dev':
        return {p: 'git' for p in pkg_names}
    if profile == 'py10x-dev':
        return {CORE: 'local', **{s: 'git' for s in others}}
    if profile == 'py10x-core-dev':
        return {p: 'local' for p in pkg_names}
    raise ValueError(f'unknown profile {profile!r}')


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


def _pip_extras_args(uv_args: list[str] | tuple[str, ...]) -> list[str]:
    """Extract `--all-extras` / `--extra` flags to forward onto a package install source."""
    out: list[str] = []
    i = 0
    args = list(uv_args)
    while i < len(args):
        a = args[i]
        if a == '--all-extras':
            out.append(a)
            i += 1
        elif a == '--extra':
            if i + 1 >= len(args):
                raise ValueError('--extra requires a value')
            out.extend([a, args[i + 1]])
            i += 2
        elif a.startswith('--extra='):
            out.append(a)
            i += 1
        else:
            i += 1
    return out


# --------------------------------------------------------------------------------------------
# installed-source detection (PEP 610) + reinstall decision
# --------------------------------------------------------------------------------------------
def source_version(src: Path) -> str:
    """Version of the package source tree at `src`.

    Must honor that package's tag filter — bare ``python -m setuptools_scm`` at the py10x root
    has no ``[tool.setuptools_scm]`` and will pick the nearest tag of *any* name (e.g. a
    ``py10x-fin-base-v*`` tag), which falsely looks like core version drift. Hatch-vcs packages
    declare ``git_describe_command`` (with ``--match``) under ``[tool.hatch.version]``; C++
    packages use ``[tool.setuptools_scm]`` in their own pyproject (CLI from that cwd).
    """
    from setuptools_scm import get_version

    pyproject = src / 'pyproject.toml'
    if not pyproject.is_file():
        return get_version(root=src)

    import tomlkit

    doc = tomlkit.parse(pyproject.read_text(encoding='utf-8'))
    tool = doc.get('tool', {})
    # C++ / scikit-build packages: CLI loads [tool.setuptools_scm] (root, describe match).
    if 'setuptools_scm' in tool:
        return subprocess.check_output([sys.executable, '-m', 'setuptools_scm'], cwd=src, text=True, stderr=subprocess.DEVNULL).strip()

    hatch_ver = tool.get('hatch', {}).get('version', {})
    if hatch_ver.get('source') == 'vcs':
        raw = hatch_ver.get('raw-options') or {}
        describe = raw.get('git_describe_command')
        rel_root = raw.get('root', '.')
        scm_root = (src / str(rel_root)).resolve()
        if describe:
            return get_version(root=scm_root, git_describe_command=str(describe))
        return get_version(root=scm_root)

    return get_version(root=src)


def _sibling_pin(name: str) -> str | None:
    """Forward pin specifier for sibling `name` from core's pyproject, or None when absent."""
    from dev_10x.xx_helpers import PyProjectHelpers

    try:
        return PyProjectHelpers.dependency_spec(PROJECT_ROOT / 'pyproject.toml', name)
    except KeyError:
        return None


def need_install(name: str, kind: str, pkg: dict, *, verbose: bool = True, installs: InstalledSourceHelpers | None = None) -> bool:
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
            except Exception as e:  # noqa: BLE001 - any failure -> reinstall
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
        '--config-settings-package',
        f'{name}:cmake.args=-T',
        '--config-settings-package',
        f'{name}:cmake.args=v143,version=14.44',
    ]


def _no_build_isolation_packages(src_dir: Path) -> list[str]:
    """`[tool.uv] no-build-isolation-package` from a packaging root (e.g. fin-base → cxx).

    `uv pip install` does not read this from the target pyproject the way `uv sync` does, so
    uv-sync must forward the names as `--no-build-isolation-package` flags.
    """
    import tomllib

    pyproject = Path(src_dir) / 'pyproject.toml'
    if not pyproject.is_file():
        return []
    raw = tomllib.loads(pyproject.read_text(encoding='utf-8')).get('tool', {}).get('uv', {}).get('no-build-isolation-package', [])
    return [str(n) for n in raw]


def _workspace_member_paths(src_dir: Path) -> dict[str, Path]:
    """`{dist-name: path}` for each `[tool.uv.workspace]` member under a packaging root."""
    import tomllib

    root = Path(src_dir)
    pyproject = root / 'pyproject.toml'
    if not pyproject.is_file():
        return {}
    patterns = tomllib.loads(pyproject.read_text(encoding='utf-8')).get('tool', {}).get('uv', {}).get('workspace', {}).get('members', [])
    out: dict[str, Path] = {}
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            member = path / 'pyproject.toml'
            if not member.is_file():
                continue
            name = tomllib.loads(member.read_text(encoding='utf-8')).get('project', {}).get('name')
            if name:
                out[str(name)] = path.resolve()
    return out


def install_mode() -> str:
    raw = os.environ.get('XX_UV_INSTALL_MODE', 'editable').strip()
    if raw not in INSTALL_MODES:
        raise ValueError(f'XX_UV_INSTALL_MODE must be one of {INSTALL_MODES}, got {raw!r}')
    return raw


def _incremental_flags(name: str, venv: Path, *, verbose: bool) -> list[str]:
    """No-isolation incremental rebuild flags for a local C++ package (mode 'incremental'/
    'incremental_quiet'). Build type comes from XX_UV_BUILD_TYPE (default Release); each type
    gets its own build dir so switching Debug<->Release does not force a full reconfigure/rebuild."""
    build_type = os.getenv('XX_UV_BUILD_TYPE', 'Release')
    build_dir = f'{(venv / "py10x-build" / name / build_type).as_posix()}/{{wheel_tag}}'
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


def install_local(name: str, pkg: dict, pin: str | None, mode: str, verbose: bool, extras_args: list[str] | tuple[str, ...] = ()) -> None:
    # Downstream native deps (e.g. fin-base → cxxfin): install workspace members listed in
    # `[tool.uv] no-build-isolation-package` *directly* first. Installing only via the parent
    # `-e xx_fin` leaves `editable.rebuild`'s persistent build-dir without CMakeCache.txt.
    # (Downstream workspace members always install editable, regardless of `mode` - out of scope
    # for XX_UV_INSTALL_MODE, which targets py10x-kernel/py10x-infra specifically.)
    if pkg.get('downstream'):
        members = _workspace_member_paths(pkg['local'])
        for n in _no_build_isolation_packages(pkg['local']):
            member = members.get(n)
            if member is None:
                print(f'  warning: {n} in no-build-isolation-package but not a workspace member of {pkg["local"]}')
                continue
            print(f'  {n}: editable (no-build-isolation, workspace member of {name})')
            margs = ['-e', str(member), f'--reinstall-package={n}', '--no-build-isolation-package', n]
            margs += _windows_cxx_cmake_flags(n)
            if verbose:
                margs.append('--verbose')
            _pip_install(*margs)

    editable = mode != 'normal'
    args = ['-e', str(pkg['local'])] if editable else [str(pkg['local'])]
    if pin:
        args.append(f'{name} ({pin})')
    args.append(f'--reinstall-package={name}')
    if pkg['cxx']:
        args += _windows_cxx_cmake_flags(name)
    if mode in ('incremental', 'incremental_quiet') and pkg['cxx']:
        args += _incremental_flags(name, PROJECT_ROOT / '.venv', verbose=(mode == 'incremental'))
    # Keep no-isolation flags on the parent install too (transitive rebuilds / metadata).
    if pkg.get('downstream'):
        for n in _no_build_isolation_packages(pkg['local']):
            args.extend(['--no-build-isolation-package', n])
        # `--all-extras` / `--extra` require an explicit requirements/pyproject source (same as
        # core step 2). Forward them onto the downstream pyproject so extras like fin-base `bbg`
        # are installed — bare `-e path --all-extras` is rejected by uv.
        if extras_args:
            args.extend([*extras_args, '--requirements', str(Path(pkg['local']) / 'pyproject.toml')])
    if verbose:
        args.append('--verbose')
    _pip_install(*args)


def install_git(name: str, pkg: dict, branch: str, extras_args: list[str] | tuple[str, ...] = ()) -> None:
    git_url = _normalize_git_url(pkg['git'])
    spec = f'{name} @ git+{git_url}@{branch}'
    if pkg['subdir']:
        spec += f'#subdirectory={pkg["subdir"]}'
    args = [spec, f'--reinstall-package={name}']
    if pkg['cxx']:
        args += _windows_cxx_cmake_flags(name)
    if pkg.get('downstream') and extras_args:
        raise RuntimeError(
            f'{name}: --all-extras/--extra on a git downstream install is unsupported; '
            f'use a local checkout so uv can read its pyproject.toml (got {list(extras_args)})'
        )
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
    print(f'uv-sync: waiting for coordinated sibling pins on branch {branch!r}{refresh} (timeout={timeout}s, interval={interval}s)...')
    code = xx_ci.wait_sibling_branch_ready(PROJECT_ROOT, branch, sync_base=sync_base, verbose=True)
    if code:
        raise SystemExit(code)
    print(f'uv-sync: sibling pins ready on branch {branch!r}')


def uv_sync(profile: str, *uv_args: str) -> None:
    tomlkit = ensure_env_and_runtime_deps(PROJECT_ROOT)
    _maybe_wait_for_sibling_branch()
    with_downstream, downstream_filter, uv_args_list = _parse_with_downstream(uv_args)
    uv_args = tuple(uv_args_list)
    all_pkgs = packages(tomlkit)
    if with_downstream:
        if downstream_filter is not None:
            pkgs = {n: p for n, p in all_pkgs.items() if not p.get('downstream') or n in downstream_filter}
        else:
            pkgs = all_pkgs
    else:
        pkgs = {n: p for n, p in all_pkgs.items() if not p.get('downstream')}
    branch = _dev10x_cfg(tomlkit).get('branch', 'main')
    kinds = profile_kinds(profile, list(pkgs))
    siblings = [p for p in pkgs if p != CORE]
    mode = install_mode()
    prev_mode = read_install_mode_state(PROJECT_ROOT)
    toggled = prev_mode is not None and prev_mode != mode

    installs = _installed_source_helpers(PROJECT_ROOT)

    print(f'uv-sync `{profile}`: ' + ', '.join(f'{p}={kinds[p]}' for p in pkgs))
    if toggled:
        print(f'XX_UV_INSTALL_MODE toggled ({prev_mode} -> {mode}): forcing rebuild of local C++ packages.')

    # Seed the C++ toolchain for incremental siblings, or when a local downstream declares
    # `[tool.uv] no-build-isolation-package` (fin-base → cxx) — those installs run in step 1
    # before `--all-extras` would otherwise pull cmake/ninja via core's dev extra.
    toolchain_reasons: list[str] = []
    if mode in ('incremental', 'incremental_quiet') and any(kinds[s] == 'local' and pkgs[s]['cxx'] for s in siblings):
        toolchain_reasons.append(f'XX_UV_INSTALL_MODE={mode} siblings')
    if any(pkgs[s].get('downstream') and kinds[s] == 'local' and _no_build_isolation_packages(pkgs[s]['local']) for s in siblings):
        toolchain_reasons.append('downstream no-build-isolation-package')
    if toolchain_reasons:
        print(f'Seeding C++ build toolchain ({", ".join(toolchain_reasons)}).')
        _pip_install('--quiet', *CXX_BUILD_TOOLCHAIN)
    verbose = '--verbose' in uv_args
    # 1. siblings / opt-in downstreams (local/git). Index siblings are handled by step 2; force a
    #    swap there only if the sibling is currently installed from a non-index source.
    print('1. siblings' + (' + downstreams' if with_downstream else '') + ':')
    extras_args = _pip_extras_args(uv_args)
    index_swaps = sync_siblings(branch, mode, installs, kinds, pkgs, siblings, toggled, verbose, extras_args)

    # 2. core's deps (additive: keeps the local/git siblings from step 1; pulls/refreshes index
    #    siblings). Extras are NOT forced - pass `--all-extras` / `--extra X` as uv-sync args; they
    #    bind to this `--requirements` source *and* are forwarded onto opt-in downstream installs.
    print('2. core deps:')
    reinstall = [f'--reinstall-package={s}' for s in index_swaps]
    _pip_install('--requirements', 'pyproject.toml', *reinstall, *uv_args)

    # 3. py10x-core itself. Always editable (see XX_UV_INSTALL_MODE's docstring above) - `mode`
    #    only governs the C++ siblings.
    print('3. py10x-core:')
    ck = kinds[CORE]
    if ck == 'git':
        install_git(CORE, pkgs[CORE], branch)
    elif need_install(CORE, 'local', pkgs[CORE], installs=installs):
        install_local(CORE, pkgs[CORE], pin=None, mode='editable', verbose=verbose)  # pure Python

    # Guard: a local sibling that came back non-editable (in an editable-expecting mode) means a
    # pin pulled an index/other build. Not meaningful in 'normal' mode, which installs non-editable
    # by design.
    if mode != 'normal':
        for s in siblings:
            if kinds[s] == 'local' and installs.installed_source(s)[0] != 'local':
                raise RuntimeError(
                    f'{s}: expected an editable local install but it is '
                    f"{installs.installed_source(s)[0]!r} - py10x-core's pin likely pulled a non-editable build"
                )

    persist_profile(PROJECT_ROOT, profile)
    persist_install_mode_state(PROJECT_ROOT, mode)
    print(f'uv-sync `{profile}` done.')


def sync_siblings(branch, mode, installs, kinds, pkgs, siblings, toggled, verbose, extras_args: list[str] | tuple[str, ...] = ()):
    index_swaps: list[str] = []
    for s in siblings:
        kind = kinds[s]
        if kind == 'index':
            if installs.installed_source(s)[0] not in (None, 'index'):
                index_swaps.append(s)
            print(f'  {s}: index (resolved with core deps in step 2{" - forcing swap" if s in index_swaps else ""})')
            continue
        do = need_install(s, kind, pkgs[s], installs=installs)
        if not do and toggled and kind == 'local' and pkgs[s]['cxx']:
            print(f'  {s}: reinstall - install mode changed (XX_UV_INSTALL_MODE)')
            do = True
        if do:
            if kind == 'local':
                # Downstream is not a core published dep — no forward pin to apply.
                pin = None if pkgs[s].get('downstream') else _sibling_pin(s)
                install_local(s, pkgs[s], pin=pin, mode=mode, verbose=verbose, extras_args=extras_args)
            else:  # git
                install_git(s, pkgs[s], branch, extras_args=extras_args)
        elif pkgs[s].get('downstream') and extras_args and kind == 'local':
            # Already installed: still apply requested extras (e.g. fin-base `bbg`) without a full reinstall.
            print(f'  {s}: ensuring extras ({" ".join(extras_args)})')
            local = Path(pkgs[s]['local'])
            _pip_install('-e', str(local), *extras_args, '--requirements', str(local / 'pyproject.toml'))
    return index_swaps


# --------------------------------------------------------------------------------------------
# profile persistence (informational; uv-run no longer needs it)
# --------------------------------------------------------------------------------------------
def persist_profile(project_root: Path, profile: str) -> None:
    (project_root / PROFILE_FILE).write_text(profile + '\n', encoding='utf-8')


def read_persisted_profile(project_root: Path) -> str:
    f = project_root / PROFILE_FILE
    return f.read_text().strip() if f.is_file() else ''


def _install_mode_marker(project_root: Path) -> Path:
    # In .venv so it tracks the install mode of the *currently installed* C++ packages and
    # resets whenever the venv is recreated.
    return project_root / '.venv' / '.xx_uv_install_mode'


def read_install_mode_state(project_root: Path) -> str | None:
    f = _install_mode_marker(project_root)
    return f.read_text().strip() if f.is_file() else None


def persist_install_mode_state(project_root: Path, mode: str) -> None:
    _install_mode_marker(project_root).write_text(mode)


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


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in PROFILES:
        print(f'Usage: uv-sync {"|".join(PROFILES)} [--with-downstream [name…]] [extra `uv pip install` options]')
        return
    profile = sys.argv[1]
    uv_sync(profile, *sys.argv[2:])
    if profile == 'py10x-core-dev':
        ensure_chromium_installed()


if __name__ == '__main__':
    main()
