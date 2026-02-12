from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
import importlib.metadata as md

from tomlkit import document, dumps, inline_table, table, TOMLDocument

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
    uv_sources = PROFILES[user_profile]
    if not uv_sources:
        return None

    doc = document()
    doc['tool'] = tool_tbl = table()
    tool_tbl['uv'] = uv_tbl = table()
    uv_tbl['sources'] = sources_tbl = table()

    for package, source in uv_sources.items():
        it = inline_table()
        # Stable key order for readability
        for k in sorted(source.keys()):
            it[k] = source[k]
        sources_tbl[package] = it

    return doc


def uv_sync(user_profile: str, *args):
    project_root = Path('.').resolve()
    pyproject = project_root / 'pyproject.toml'

    if not pyproject.exists():
        raise RuntimeError('pyproject.toml not found')

    py_bak = pyproject.with_suffix('.toml.bak')

    if py_bak.exists():
        raise RuntimeError(f'Backup already exists: {py_bak}')

    src_block = uv_sources_block(user_profile)
    try:
        if src_block is not None:
            shutil.copy2(pyproject, py_bak)
            with pyproject.open('a', encoding='utf-8', newline='\n') as f:
                f.write('\n' + src_block.as_string())
        subprocess.run(['uv', 'sync', *args], cwd=project_root, check=True)

    finally:
        if src_block is not None and py_bak.exists():
            shutil.copy2(py_bak, pyproject)
            py_bak.unlink(missing_ok=True)


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
        print(f'Usage: uvx --from "10x-universe[dev]" uv_sync {"|".join(PROFILES)} [uv sync options (see uv sync --help for details)]')
    else:
        profile = sys.argv[1]
        sources = uv_sources_block(profile)
        s = dumps(sources['tool']['uv']['sources']) if sources else ''
        print(f'Using the {"following" if s else "default"} sources for `{profile}` profile{":" if s else "."}\n{s}')
        if opts := get_extra_options(profile):
            print(f'Using the following extra options for `{profile}` profile: {opts}')

        uv_sync(profile, *sys.argv[2:], *opts)
        if profile == 'py10x-core-dev':
            ensure_chromium_installed()


if __name__ == '__main__':
    main()
