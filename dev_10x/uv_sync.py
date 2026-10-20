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
  1. siblings / opt-in downstreams (local/git) - install only if the reinstall rules say so.
     `--all-extras` / `--extra` are forwarded onto *local* downstream installs only
     (they need a pyproject source; git specs have none, and siblings are never extras).
  2. `uv pip install --requirements pyproject.toml` (+ caller args such as `--all-extras`) -
     current package's deps+extras, additive;
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

# XX_UV_INSTALL_MODE controls how local C++ packages (py10x-kernel/py10x-infra, and downstream
# members like cxxfin) get installed. Every mode builds without isolation into the persistent
# build-dir each package's pyproject sets (build/py10x-build/<pkg>/<build type>/<wheel tag>):
#   normal            plain, non-editable build+install - no ongoing dependency on the sibling's
#                      source tree; right for a build-once image/CI run.
#   editable          editable install; C++ edits need a re-install (incremental, via the cache).
#   incremental       editable + rebuild-on-*import* (not just at install time): C++ edits take
#                      effect on the next import.
#   incremental_quiet (default) same as incremental, with scikit-build-core's per-import
#                      rebuild-check log spam silenced (editable.verbose=false).
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

    py10x-core is the repo root; siblings (`[tool.dev_10x.siblings]`, `cxx=True`) and optional
    downstreams (`[tool.dev_10x.downstream]`, `cxx=False`, omitted from default sync) are in-tree
    subdirectories, so their git source is this repo's remote + `subdirectory=path`.
    """
    remote = _git_remote()
    pkgs: dict[str, dict] = {
        CORE: {'local': PROJECT_ROOT, 'git': remote, 'subdir': None, 'cxx': False, 'downstream': False},
    }
    cfg = _dev10x_cfg(tomlkit)
    for downstream, table in ((False, 'siblings'), (True, 'downstream')):
        for name, spec in cfg.get(table, {}).items():
            rel = PurePosixPath(spec['path'])
            if '..' in rel.parts:
                raise SystemExit(f'[tool.dev_10x.{table}] {name}: path {spec["path"]!r} must be inside this repo')
            pkgs[name] = {
                'local': (PROJECT_ROOT / spec['path']).resolve(),
                'git': spec.get('git') or remote,
                'subdir': spec.get('subdirectory', None if rel.parts in ((), ('.',)) else str(rel)),
                'cxx': not downstream,  # siblings are the compiled C++ packages
                'downstream': downstream,
            }
    return pkgs


def profile_kinds(profile: str, pkg_names: list[str]) -> dict[str, str]:
    """Desired source kind ('local'|'git'|'index') per package for `profile`."""
    others = [p for p in pkg_names if p != CORE]
    if profile == 'user':
        return {CORE: 'local', **{s: 'index' for s in others}}
    if profile == 'domain-dev':
        return {p: 'git' for p in pkg_names}
    if profile in ('py10x-dev', 'py10x-core-dev'):  # py10x-core-dev: legacy alias
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
    """Extract `--all-extras` / `--extra` flags to forward onto a local downstream install."""
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


def _no_root_sources() -> list[str]:
    """`--no-sources-package` for each sibling, for the installs that resolve py10x-core's own deps
    (`--requirements pyproject.toml`, `-e .`): uv-sync picks a sibling's source itself (profile +
    XX_UV_INSTALL_MODE), so the root's editable `[tool.uv.sources]` for it must not apply there.
    Not on every install: with any `--no-sources-package`, uv rejects xx_fin's workspace source for
    py10x-fin-base-cxx ("not a workspace member") when installing the fin-base downstream."""
    import tomllib

    doc = tomllib.loads((PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    siblings = doc.get('tool', {}).get('dev_10x', {}).get('siblings', {})
    return [arg for name in siblings for arg in ('--no-sources-package', name)]


def _pip_install(*args: str) -> None:
    """`uv pip install` with the mandatory constraints freeze applied."""
    _run(['uv', 'pip', 'install', *args, *CONSTRAINTS])


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


def _is_native(src_dir: Path) -> bool:
    """A C++ (scikit-build-core) package, as opposed to a pure-Python one."""
    import tomllib

    pyproject = Path(src_dir) / 'pyproject.toml'
    if not pyproject.is_file():
        return False
    backend = tomllib.loads(pyproject.read_text(encoding='utf-8')).get('build-system', {}).get('build-backend', '')
    return backend.startswith('scikit_build_core')


def _native_members(src_dir: Path) -> dict[str, Path]:
    """`{dist-name: path}` for the C++ workspace members of a downstream (fin-base → cxxfin).

    They build without isolation (their pyprojects set a persistent build-dir) via the root
    pyproject's `[tool.uv] no-build-isolation-package`, which `uv pip install` reads from the cwd
    (the py10x root); the downstream's own list covers a plain `uv sync` inside it. Both lists are
    checked by test_uv_sync's TestNoBuildIsolationLists.
    """
    return {n: p for n, p in _workspace_member_paths(src_dir).items() if _is_native(p)}


def install_mode() -> str:
    raw = os.environ.get('XX_UV_INSTALL_MODE', 'incremental_quiet').strip()
    if raw not in INSTALL_MODES:
        raise ValueError(f'XX_UV_INSTALL_MODE must be one of {INSTALL_MODES}, got {raw!r}')
    return raw


def _cxx_build_flags(name: str, mode: str) -> list[str]:
    """Build flags for a local C++ package (sibling or downstream member) in any install mode.

    The package's own pyproject sets the defaults, matching `incremental_quiet`: a persistent
    build-dir plus quiet rebuild-on-import; the other modes only override the rebuild settings.
    Every mode builds without isolation (an isolated build would bake throwaway cmake/ninja paths
    into that CMakeCache) via the root pyproject's `[tool.uv] no-build-isolation-package`. The build
    type is the pyproject's `cmake.build-type`; override with SKBUILD_CMAKE_BUILD_TYPE (it reaches
    the build through the environment, as it does for a plain `uv pip install`)."""
    flags: list[str] = []
    if mode == 'editable':
        flags += ['--config-settings-package', f'{name}:editable.rebuild=false']
    elif mode == 'incremental':
        flags += ['--config-settings-package', f'{name}:editable.verbose=true']
    return flags


def install_local(name: str, pkg: dict, pin: str | None, mode: str, verbose: bool, extras_args: list[str] | tuple[str, ...] = ()) -> None:
    # Downstream native deps (e.g. fin-base → cxxfin): install its C++ workspace members *directly*
    # first. Installing only via the parent
    # `-e xx_fin` leaves `editable.rebuild`'s persistent build-dir without CMakeCache.txt.
    # Members follow XX_UV_INSTALL_MODE like py10x-kernel/py10x-infra.
    editable = mode != 'normal'
    member_flags: list[str] = []
    if pkg.get('downstream'):
        for n, member in _native_members(pkg['local']).items():
            print(f'  {n}: {mode} (workspace member of {name})')
            flags = _cxx_build_flags(n, mode)
            member_flags += flags
            margs = (['-e', str(member)] if editable else [str(member)]) + [f'--reinstall-package={n}', *flags]
            if verbose:
                margs.append('--verbose')
            _pip_install(*margs)

    args = ['-e', str(pkg['local'])] if editable else [str(pkg['local'])]
    if pin:
        args.append(f'{name} ({pin})')
    args.append(f'--reinstall-package={name}')
    if pkg['cxx']:
        args += _cxx_build_flags(name, mode)
    if name == CORE:
        args += _no_root_sources()
    # Keep the members' flags on the parent install too (transitive rebuilds / metadata), so a
    # rebuild triggered via the parent uses the same build dir and rebuild settings.
    if pkg.get('downstream'):
        args.extend(member_flags)
        # `--all-extras` / `--extra` require an explicit requirements/pyproject source (same as
        # core step 2). Forward them onto the downstream pyproject so extras like fin-base `bbg`
        # are installed — bare `-e path --all-extras` is rejected by uv. Downstreams must be local.
        if extras_args:
            args.extend([*extras_args, '--requirements', str(Path(pkg['local']) / 'pyproject.toml')])
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
        # Isolated, non-editable build from uv's git checkout: throwaway build dir instead of the
        # pyproject's persistent one (which would land inside uv's cache); rebuild needs the latter.
        args += ['--config-settings-package', f'{name}:build-dir=', '--config-settings-package', f'{name}:editable.rebuild=false']
    _pip_install(*args)


# --------------------------------------------------------------------------------------------
# the sync
# --------------------------------------------------------------------------------------------
def uv_sync(profile: str, *uv_args: str) -> None:
    tomlkit = ensure_env_and_runtime_deps(PROJECT_ROOT)
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
    # Opt-in downstreams are always the local packaging root (in-tree xx_fin, etc.).
    # Profile git/index applies to siblings only — extras need a pyproject on disk.
    for n, p in pkgs.items():
        if p.get('downstream'):
            kinds[n] = 'local'
    siblings = [p for p in pkgs if p != CORE]
    mode = install_mode()
    state = install_state(mode)
    prev_state = read_install_mode_state(PROJECT_ROOT)
    toggled = prev_state is not None and prev_state != state

    installs = _installed_source_helpers(PROJECT_ROOT)

    print(f'uv-sync `{profile}`: ' + ', '.join(f'{p}={kinds[p]}' for p in pkgs))
    if toggled:
        print(f'install mode / build type changed ({prev_state} -> {state}): forcing rebuild of local C++ packages.')

    # Seed the C++ toolchain for local C++ siblings (non-isolated builds in every mode), or when a
    # local downstream has C++ workspace members (fin-base → cxx) — those
    # installs run in step 1 before `--all-extras` would otherwise pull cmake/ninja via core's dev
    # extra.
    toolchain_reasons: list[str] = []
    if any(kinds[s] == 'local' and pkgs[s]['cxx'] for s in siblings):
        toolchain_reasons.append('local C++ siblings')
    if any(pkgs[s].get('downstream') and kinds[s] == 'local' and _native_members(pkgs[s]['local']) for s in siblings):
        toolchain_reasons.append('downstream C++ members')
    if toolchain_reasons:
        print(f'Seeding C++ build toolchain ({", ".join(toolchain_reasons)}).')
        _pip_install('--quiet', *CXX_BUILD_TOOLCHAIN)
    verbose = '--verbose' in uv_args
    # 1. siblings / opt-in downstreams (local/git). Index siblings are handled by step 2; force a
    #    swap there only if the sibling is currently installed from a non-index source.
    print('1. siblings' + (' + downstreams' if with_downstream else '') + ':')
    extras_args = _pip_extras_args(uv_args)
    index_swaps = sync_siblings(branch, mode, installs, kinds, pkgs, siblings, toggled, verbose, extras_args)

    # 2. current package deps (additive: keeps the local/git siblings from step 1; pulls/refreshes
    #    index siblings). Extras are NOT forced - pass `--all-extras` / `--extra X` as uv-sync args;
    #    they bind to this `--requirements` source *and* to local opt-in downstream installs.
    print('2. core deps:')
    reinstall = [f'--reinstall-package={s}' for s in index_swaps]
    _pip_install('--requirements', 'pyproject.toml', *reinstall, *_no_root_sources(), *uv_args)

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
    persist_install_mode_state(PROJECT_ROOT, state)
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
        # A mode change also applies to a local downstream's native members (fin-base → cxxfin).
        has_cxx = pkgs[s]['cxx'] or (pkgs[s].get('downstream') and _native_members(pkgs[s]['local']))
        if not do and toggled and kind == 'local' and has_cxx:
            print(f'  {s}: reinstall - install mode or build type changed')
            do = True
        downstream_extras = extras_args if pkgs[s].get('downstream') else ()
        if do:
            if kind == 'local':
                # Downstream is not a core published dep — no forward pin to apply.
                pin = None if pkgs[s].get('downstream') else _sibling_pin(s)
                install_local(s, pkgs[s], pin=pin, mode=mode, verbose=verbose, extras_args=downstream_extras)
            else:  # git
                if downstream_extras:
                    raise RuntimeError(
                        f'{s}: --all-extras/--extra on a git downstream install is unsupported; '
                        f'downstreams must be local so uv can read their pyproject.toml (got {list(downstream_extras)})'
                    )
                install_git(s, pkgs[s], branch)
        elif downstream_extras and kind == 'local':
            # Already installed: still apply requested extras (e.g. fin-base `bbg`) without a full reinstall.
            print(f'  {s}: ensuring extras ({" ".join(downstream_extras)})')
            local = Path(pkgs[s]['local'])
            _pip_install('-e', str(local), *downstream_extras, '--requirements', str(local / 'pyproject.toml'))
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


def install_state(mode: str) -> str:
    """`<mode>:<build type>` of the C++ packages being installed. The build type is the
    SKBUILD_CMAKE_BUILD_TYPE override, or `default` (the packages' pyproject `cmake.build-type`)."""
    return f'{mode}:{os.environ.get("SKBUILD_CMAKE_BUILD_TYPE", "").strip() or "default"}'


def read_install_mode_state(project_root: Path) -> str | None:
    f = _install_mode_marker(project_root)
    if not f.is_file():
        return None
    state = f.read_text().strip()
    return state if ':' in state else f'{state}:default'  # marker written before build types were tracked


def persist_install_mode_state(project_root: Path, state: str) -> None:
    _install_mode_marker(project_root).write_text(state)


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
    if profile in ('py10x-dev', 'py10x-core-dev'):
        ensure_chromium_installed()


if __name__ == '__main__':
    main()
