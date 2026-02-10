from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from tomlkit import document, dumps, inline_table, table, TOMLDocument

ROOTS = {
    'py10x-universe': {'path': '../py10x', 'editable': True},
    'py10x-core': {'path': '../cxx10x/core_10x', 'editable': True},
    'py10x-infra': {'path': '../cxx10x/infra_10x', 'editable': True},
}

# UPDATED: uv-native git source shape
REPOS = {
    'py10x-universe': {
        'git': 'https://github.com/10x-software/py10x.git',
        'branch': 'main',
    },
    'py10x-core': {
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
    'py10x-dev': REPOS | {'py10x-universe': ROOTS['py10x-universe']},
    'py10x-core-dev': ROOTS,
}
EXTRA_OPTIONS = {
    profile: [f'--reinstall-package={package}' for package, source in sources.items() if source is ROOTS.get(package)]
    for profile, sources in PROFILES.items()
}


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


def uv_sync(user_profile: str):
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
        subprocess.run(['uv', 'sync', *sys.argv[2:], *EXTRA_OPTIONS[user_profile]], cwd=project_root, check=True)

    finally:
        if src_block is not None and py_bak.exists():
            shutil.copy2(py_bak, pyproject)
            py_bak.unlink(missing_ok=True)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in PROFILES:
        print(f'Usage: uv run uv_sync {"|".join(PROFILES)} [uv sync options (see uv sync --help for details)]')
    else:
        profile = sys.argv[1]
        sources = uv_sources_block(profile)
        s = sources and dumps(sources['tool']['uv']['sources'])
        print(f'Using the {"following" if s else "default"} sources for `{profile}` profile{":" if s else "."}\n{s}')
        if opts := EXTRA_OPTIONS[profile]:
            print(f'Using the following extra options for `{profile}` profile: {opts}')

        uv_sync(profile)


if __name__ == '__main__':
    main()
