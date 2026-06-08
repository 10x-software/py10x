from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING
import importlib.metadata as md

if TYPE_CHECKING:
    from tomlkit import TOMLDocument

ROOTS = {
    'py10x-core': {'path': '../py10x', 'editable': True},
    'py10x-kernel': {'path': '../cxx10x/core_10x', 'editable': True},
    'py10x-infra': {'path': '../cxx10x/infra_10x', 'editable': True},
}

REPOS = {
    'py10x-core': {
        'git': 'https://github.com/10x-software/py10x.git',
        'branch': 'main',
    },
    'py10x-kernel': {
        'git': 'https://github.com/10x-software/cxx10x.git',
        'branch': 'main',
        'subdirectory': 'core_10x',
    },
    'py10x-infra': {
        'git': 'https://github.com/10x-software/cxx10x.git',
        'branch': 'main',
        'subdirectory': 'infra_10x',
    },
}

PROFILES = {
    'user': {},
    'domain-dev': REPOS,
    'py10x-dev': REPOS | {'py10x-core': ROOTS['py10x-core']},
    'py10x-core-dev': ROOTS,
}

CXX_BUILD_TOOLCHAIN = ['scikit-build-core', 'setuptools-scm', 'cmake', 'ninja', 'editables']

PROFILE_FILE = '.dev_10x_profile'


def persist_profile(project_root: Path, profile: str) -> None:
    (project_root / PROFILE_FILE).write_text(profile + '\n', encoding='utf-8')


def read_persisted_profile(project_root: Path) -> str:
    f = project_root / PROFILE_FILE
    if not f.is_file():
        raise RuntimeError(
            f'{PROFILE_FILE} not found - run `uv-sync <profile>` first so `uv-run` knows '
            f'which source override to apply.')
    return f.read_text(encoding='utf-8').strip()


def _load_pyproject(path: Path):
    import tomlkit
    return tomlkit.parse(path.read_text(encoding='utf-8'))


def cxx_package_dirs(profile: str, project_root: Path) -> dict[str, Path]:
    dirs: dict[str, Path] = {}
    for pkg, src in PROFILES[profile].items():
        if src is ROOTS.get(pkg) and 'cxx10x' in str(src.get('path', '')):
            dirs[pkg] = (project_root / src['path']).resolve()
    # (b) in-repo workspace members (e.g. cxxfin); member dir name == package name
    try:
        data = _load_pyproject(project_root / 'pyproject.toml')
    except Exception:
        return dirs
    members = (data.get('tool', {}).get('uv', {}).get('workspace', {}) or {}).get('members', [])
    for pattern in members:
        for member_dir in sorted(project_root.glob(str(pattern))):
            if (member_dir / 'pyproject.toml').is_file():
                dirs[member_dir.name] = member_dir.resolve()
    return dirs

def ensure_env_and_runtime_deps(project_root) -> ModuleType:
    if not (project_root / '.venv' / 'pyvenv.cfg').is_file():
        subprocess.run(['uv', 'venv'], cwd=project_root, check=True)
    try:
        import tomlkit
        import setuptools_scm  # noqa: F401
    except ImportError:
        subprocess.run(['uv', 'pip', 'install', '--python', sys.executable, '--quiet',
                        'tomlkit', 'setuptools-scm'], cwd=project_root, check=True)
        import tomlkit
    return tomlkit

def source_version(src: str) -> str:
    out = subprocess.check_output(
        [sys.executable, '-m', 'setuptools_scm'],
        cwd=src,
        text=True,
    )
    return out.strip()


def should_reinstall(dist_name: str, src: str, verbose=False, quiet=False) -> bool:
    if 'cxx10x' not in src:
        if verbose:
            print(f'No need to reinstall {dist_name} - editable installs work for python packages')
        return False

    try:
        installed = md.version(dist_name)
        new_version = source_version(src)
    except md.PackageNotFoundError as e:
        if not quiet:
            print(f'Will reinstall {dist_name} just in case: got error {e}')
        return True

    will_reinstall = installed != new_version
    if (will_reinstall or verbose) and not quiet:
        print(f'{"Will reinstall" if will_reinstall else "No need to reinstall"} {dist_name}: old_version={installed} new_version={new_version}')
    return will_reinstall


def get_extra_options(profile: str):
    return [
        f'--reinstall-package={package}'
        for package, source in PROFILES[profile].items()
        if source is ROOTS.get(package) and should_reinstall(package, source['path'])
    ]


def uv_sources_block(user_profile: str) -> TOMLDocument | None:
    import tomlkit
    uv_sources = PROFILES[user_profile]
    if not uv_sources:
        return None

    doc = tomlkit.document()
    doc['tool'] = tool_tbl = tomlkit.table()
    tool_tbl['uv'] = uv_tbl = tomlkit.table()
    uv_tbl['sources'] = sources_tbl = tomlkit.table()

    for package, source in uv_sources.items():
        it = tomlkit.inline_table()
        # Stable key order for readability
        for k in sorted(source.keys()):
            it[k] = source[k]
        sources_tbl[package] = it

    return doc


def _merge_sources(pyproject: Path, src_block, tomlkit) -> None:
    """Merge the profile's source override into the consuming pyproject (in place)."""
    doc = tomlkit.parse(pyproject.read_text(encoding='utf-8'))
    new_sources = src_block['tool']['uv']['sources']
    try:
        existing_sources = doc['tool']['uv']['sources']
    except KeyError:
        existing_sources = {}
    merged = {**existing_sources, **new_sources}  # override wins on conflict
    if 'tool' not in doc:
        doc.add('tool', tomlkit.table())
    if 'uv' not in doc['tool']:
        doc['tool'].add('uv', tomlkit.table())
    if 'sources' not in doc['tool']['uv']:
        doc['tool']['uv'].add('sources', tomlkit.table())
    sources_tbl = doc['tool']['uv']['sources']
    for k, v in merged.items():
        sources_tbl[k] = v
    pyproject.write_text(tomlkit.dumps(doc), encoding='utf-8', newline='\n')


def _incremental_flags(cxx_dirs: dict[str, Path], venv: Path) -> list[str]:
    """Per-package uv flags: disable isolation, give each its own venv-scoped build dir
    (no collision), and enable import-time rebuild — all without editing any pyproject."""
    extra: list[str] = []
    for pkg in cxx_dirs:
        build_dir = f"{(venv / 'cxx-build' / pkg).as_posix()}/{{wheel_tag}}"
        extra += ['--no-build-isolation-package', pkg,
                  '--config-settings-package', f'{pkg}:build-dir={build_dir}',
                  '--config-settings-package', f'{pkg}:editable.rebuild=true']
    return extra


def run_profile(project_root: Path, profile: str, command: str, uv_args,
                extra_options=(), seed: bool = True) -> None:
    """Transiently apply `profile`'s source override to the consuming pyproject (ALWAYS
    reverted — never a dirty pyproject), add incremental build flags for LOCAL C++
    packages when XX_UV_INCREMENTAL is set, then run `uv <command> <uv_args>`.
    Shared by `uv-sync` (command='sync') and `uv-run` (command='run')."""
    pyproject = project_root / 'pyproject.toml'
    if not pyproject.exists():
        raise RuntimeError('pyproject.toml not found')

    py_bak = pyproject.with_suffix('.toml.bak')
    if py_bak.exists():
        raise RuntimeError(f'Backup already exists: {py_bak}')

    tomlkit = ensure_env_and_runtime_deps(project_root)
    incremental = int(os.environ.get('XX_UV_INCREMENTAL', 0))
    if incremental:
        print('XX_UV_INCREMENTAL set: no-build-isolation + incremental rebuilds (local packages only).')

    src_block = uv_sources_block(profile)
    if src_block is not None:
        print(f'Overriding sources for `{profile}` profile:\n'
              f'{tomlkit.dumps(src_block["tool"]["uv"]["sources"])}')

    extra: list[str] = []
    try:
        if src_block is not None:
            shutil.copy2(pyproject, py_bak)
            _merge_sources(pyproject, src_block, tomlkit)

        if incremental and (cxx_dirs := cxx_package_dirs(profile, project_root)):
            if seed:
                # Ensure the no-isolation toolchain is in the venv for the cold metadata
                # hook and the import-time rebuild's `cmake --build` (also a dev dep, so
                # it is not pruned). Skipped for `uv-run`, which reuses the synced venv.
                subprocess.run(['uv', 'pip', 'install', '--quiet', *CXX_BUILD_TOOLCHAIN],
                               cwd=project_root, check=True)
            extra = _incremental_flags(cxx_dirs, project_root / '.venv')

        subprocess.run(['uv', command, *uv_args, *extra_options, *extra],
                       cwd=project_root, check=True)
    finally:
        if py_bak.exists():
            # ALWAYS revert: pyproject is only ever transiently modified.
            shutil.copy2(py_bak, pyproject)
            py_bak.unlink(missing_ok=True)


def uv_sync(profile: str, *uv_args):
    project_root = Path('.').resolve()
    persist_profile(project_root, profile)   # let `uv-run` re-apply the same override
    opts = get_extra_options(profile)
    if opts:
        print(f'Using the following extra options for `{profile}` profile: {opts}')
    run_profile(project_root, profile, 'sync', uv_args, extra_options=opts)


def ensure_chromium_installed() -> None:
    try:
        import playwright  # check package exists
    except ImportError:
        return  # playwright not installed → skip

    from playwright.sync_api import sync_playwright, Error as PlaywrightError

    try:
        with sync_playwright() as p:
            p.chromium.launch(headless=True)  # probe
        return  # already good
    except PlaywrightError:
        print('Installing Playwright Chromium...')
        subprocess.run(['playwright', 'install', 'chromium'], check=True)
        print('Done.')


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in PROFILES:
        print(f'Usage: uv-sync {"|".join(PROFILES)} [uv sync options (see uv sync --help for details)]')
        return
    profile = sys.argv[1]
    uv_sync(profile, *sys.argv[2:])
    if profile == 'py10x-core-dev':
        ensure_chromium_installed()


if __name__ == '__main__':
    main()
