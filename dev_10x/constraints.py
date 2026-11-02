"""`xx-constraints` - generate / verify the committed third-party dependency freeze.

The source of truth is the committed `uv.lock` (universal: every supported Python / platform, all
extras and dependency groups). `constraints.txt` is generated from it with `uv export`: the same pins
as a reviewable `name==version` list, used as `uv pip install -c constraints.txt` by the release
workflows. Never edit either by hand; change pyproject ranges and run `compile`, or let the weekly
refresh workflow upgrade them.

First-party packages are deliberately NOT exported (`_first_party()`: root, siblings, downstreams, and
`[tool.uv.workspace]` members from the repo root **and** from each sibling/downstream packaging root,
e.g. fin-base's `cxxfin` → `py10x-fin-base-cxx`). Their versions stay owned by editable/git/promote
pins, not this freeze.

Subcommands:
  compile [--upgrade] [--summary-file PATH]
           `uv lock` (keeps existing pins where still valid), or `uv lock --upgrade` (bump every pin
           to the latest version the ranges allow), then regenerate constraints.txt from uv.lock.
           --summary-file writes uv's "Updated X v1 -> v2" lines (for the refresh PR description).
  check    assert every *installed* third-party distribution is pinned in constraints.txt
  check-export
           assert constraints.txt is exactly what `uv export` produces from uv.lock

uv is invoked as `$UV` when set (uv sets it inside `uv run`), so a venv-installed uv (licensecheck
pulls one on Python 3.11) never shadows the uv that ran the command.

Kernel-free (subprocess + importlib.metadata only) so it runs before any sibling is built.
"""

from __future__ import annotations

import importlib.metadata as md
import os
import re
import subprocess
import sys
from pathlib import Path

import tomllib

PROJECT_ROOT = Path.cwd()
CONSTRAINTS = PROJECT_ROOT / 'constraints.txt'


def _normalize(name: str) -> str:
    """PEP 503 normalized distribution name."""
    return re.sub(r'[-_.]+', '-', name).lower()


def _dev10x_paths(section: str) -> dict[str, Path]:
    """{dist-name: pyproject.toml path} for each `[tool.dev_10x.{section}]` entry."""
    data = tomllib.loads((PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    entries = data.get('tool', {}).get('dev_10x', {}).get(section, {})
    return {name: (PROJECT_ROOT / spec['path'] / 'pyproject.toml') for name, spec in entries.items()}


def _siblings() -> dict[str, Path]:
    """{dist-name: pyproject.toml path} for each [tool.dev_10x.siblings] entry."""
    return _dev10x_paths('siblings')


def _downstreams() -> dict[str, Path]:
    """{dist-name: pyproject.toml path} for each [tool.dev_10x.downstream] entry."""
    return _dev10x_paths('downstream')


def _workspace_members_at(root: Path) -> set[str]:
    """Normalized [project].name of each `[tool.uv.workspace]` member under `root`."""
    pyproject = root / 'pyproject.toml'
    if not pyproject.is_file():
        return set()
    data = tomllib.loads(pyproject.read_text(encoding='utf-8'))
    patterns = data.get('tool', {}).get('uv', {}).get('workspace', {}).get('members', [])
    names: set[str] = set()
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            member = path / 'pyproject.toml'
            if member.is_file():
                name = tomllib.loads(member.read_text(encoding='utf-8')).get('project', {}).get('name')
                if name:
                    names.add(_normalize(name))
    return names


def _workspace_members() -> set[str]:
    """Workspace members from the repo root and each sibling/downstream packaging root."""
    names = _workspace_members_at(PROJECT_ROOT)
    for path in {*_siblings().values(), *_downstreams().values()}:
        names |= _workspace_members_at(path.parent)
    return names


def _first_party() -> set[str]:
    """Normalized names never pinned in the freeze: root, siblings, downstreams, workspace members."""
    data = tomllib.loads((PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    root = data['project']['name']
    return {
        _normalize(root),
        *(_normalize(n) for n in _siblings()),
        *(_normalize(n) for n in _downstreams()),
        *_workspace_members(),
    }


HEADER = '# Generated from uv.lock by `xx-constraints compile` (uv export). Do not edit by hand.\n'
_LOCK_CHANGE = re.compile(r'^\s*(Updated|Added|Removed) ')


def _uv() -> str:
    """The uv that ran us (`$UV` inside `uv run`), not whatever `uv` is first on PATH."""
    return os.environ.get('UV') or 'uv'


def _export_cmd() -> list[str]:
    no_emit = [arg for name in sorted(_first_party()) for arg in ('--no-emit-package', name)]
    return [
        _uv(),
        'export',
        '--frozen',
        '--all-extras',
        '--all-groups',
        '--no-hashes',
        '--no-header',
        '--format',
        'requirements-txt',
        *no_emit,
    ]


def _export() -> str:
    """constraints.txt content for the current uv.lock."""
    out = subprocess.run(_export_cmd(), cwd=PROJECT_ROOT, check=True, capture_output=True, text=True).stdout
    return HEADER + out


def compile_(upgrade: bool = False, summary_file: Path | None = None) -> int:
    """`uv lock [--upgrade]`, then regenerate constraints.txt from uv.lock."""
    cmd = [_uv(), 'lock', *(['--upgrade'] if upgrade else [])]
    print('$', ' '.join(cmd))
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, check=False, capture_output=True, text=True)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode:
        return result.returncode
    changes = [line.strip() for line in result.stderr.splitlines() if _LOCK_CHANGE.match(line)]
    if summary_file is not None:
        summary_file.write_text(''.join(f'{line}\n' for line in changes), encoding='utf-8')
    CONSTRAINTS.write_text(_export(), encoding='utf-8')
    print(f'xx-constraints: wrote {CONSTRAINTS.name} from uv.lock ({len(changes)} lock change(s)).')
    return 0


def check_export() -> int:
    """Fail if constraints.txt is not exactly the `uv export` of uv.lock."""
    if not CONSTRAINTS.is_file():
        sys.exit(f'xx-constraints: {CONSTRAINTS} not found - run `xx-constraints compile` first.')
    if CONSTRAINTS.read_text(encoding='utf-8') != _export():
        print('xx-constraints check-export FAILED - constraints.txt does not match uv.lock.')
        print('Regenerate with `xx-constraints compile` and commit uv.lock and constraints.txt together.')
        return 1
    print('xx-constraints check-export OK - constraints.txt matches uv.lock.')
    return 0


def _pinned_names() -> set[str]:
    if not CONSTRAINTS.is_file():
        sys.exit(f'xx-constraints: {CONSTRAINTS} not found - run `xx-constraints compile` first.')
    names: set[str] = set()
    for line in CONSTRAINTS.read_text(encoding='utf-8').splitlines():
        m = re.match(r'([A-Za-z0-9][A-Za-z0-9._-]*)\s*==', line)
        if m:
            names.add(_normalize(m.group(1)))
    return names


def check() -> int:
    """Fail if any installed third-party distribution is not pinned in constraints.txt."""
    pinned = _pinned_names()
    exclude = _first_party()
    installed = {_normalize(d.name): d.version for d in md.distributions() if d.name}
    uncovered = sorted(n for n in installed if n not in pinned and n not in exclude)
    if uncovered:
        print('xx-constraints check FAILED - installed but not pinned in constraints.txt:')
        for n in uncovered:
            print(f'  {n}=={installed[n]}')
        print('Regenerate with `xx-constraints compile` and commit uv.lock and constraints.txt.')
        return 1
    print(f'xx-constraints check OK - all {len(installed) - len(exclude & set(installed))} third-party distributions are pinned.')
    return 0


USAGE = 'Usage: xx-constraints [compile [--upgrade] [--summary-file PATH]|check|check-export]'


def main() -> None:
    args = sys.argv[1:]
    if not args:
        sys.exit(compile_())
    cmd, rest = args[0], args[1:]
    if cmd == 'compile':
        summary_file = None
        if '--summary-file' in rest:
            k = rest.index('--summary-file')
            if k + 1 >= len(rest):
                print(USAGE, file=sys.stderr)
                sys.exit(2)
            summary_file = Path(rest[k + 1])
        sys.exit(compile_(upgrade='--upgrade' in rest, summary_file=summary_file))
    if cmd == 'check':
        sys.exit(check())
    if cmd == 'check-export':
        sys.exit(check_export())
    sys.exit(USAGE)


if __name__ == '__main__':
    main()
