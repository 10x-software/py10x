"""`xx-constraints` - generate / verify the committed third-party dependency freeze.

`constraints.txt` pins the *full third-party transitive graph* of py10x-core **and** its C++ siblings
(py10x-kernel / py10x-infra), so dev and CI installs are reproducible. It is applied via
`uv pip install -c constraints.txt` on every install (see `dev_10x/uv_sync.py` and the CI workflows).

First-party packages are deliberately NOT pinned here: py10x-core is the project root (uv never
self-emits it; its test-group reverse dep is a PEP 735 group, not pulled by `uv pip compile`), and the
siblings are `--no-emit`'d. The excluded set is derived (`_first_party`) from the root [project].name,
[tool.dev_10x.siblings], and any [tool.uv.workspace] members - not a hardcoded list - so it stays in
sync as packages are added. Their versions are owned by the sibling-source profiles and the xx-promote
pin model, not by this freeze.

Subcommands:
  compile  (default) regenerate constraints.txt from py10x's + both siblings' pyproject.toml.
           Needs the ../cxx10x checkout (a precondition of `uv-sync py10x-core-dev`).
  check    assert every *installed* third-party distribution is pinned in constraints.txt - i.e. the
           env is fully frozen. Catches a py10x OR a sibling dependency that escaped the freeze.

Kernel-free (subprocess + importlib.metadata only) so it runs before any sibling is built.
"""
from __future__ import annotations

import importlib.metadata as md
import re
import subprocess
import sys
import tomllib
from pathlib import Path

PROJECT_ROOT = Path('.').resolve()
CONSTRAINTS = PROJECT_ROOT / 'constraints.txt'


def _normalize(name: str) -> str:
    """PEP 503 normalized distribution name."""
    return re.sub(r'[-_.]+', '-', name).lower()


def _siblings() -> dict[str, Path]:
    """{dist-name: pyproject.toml path} for each [tool.dev_10x.siblings] entry."""
    data = tomllib.loads((PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    sibs = data.get('tool', {}).get('dev_10x', {}).get('siblings', {})
    return {name: (PROJECT_ROOT / spec['path'] / 'pyproject.toml') for name, spec in sibs.items()}


def _workspace_members() -> set[str]:
    """Normalized [project].name of each [tool.uv.workspace] member (empty if no workspace)."""
    data = tomllib.loads((PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    patterns = data.get('tool', {}).get('uv', {}).get('workspace', {}).get('members', [])
    names: set[str] = set()
    for pattern in patterns:
        for path in sorted(PROJECT_ROOT.glob(pattern)):
            member = path / 'pyproject.toml'
            if member.is_file():
                name = tomllib.loads(member.read_text(encoding='utf-8')).get('project', {}).get('name')
                if name:
                    names.add(_normalize(name))
    return names


def _first_party() -> set[str]:
    """Normalized names never pinned in the freeze: the root project, its [tool.dev_10x.siblings],
    and any [tool.uv.workspace] members. Owned by the profile system / xx-promote, not this freeze."""
    data = tomllib.loads((PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    root = data['project']['name']
    return {_normalize(root), *(_normalize(n) for n in _siblings()), *_workspace_members()}


def _python_floor() -> str:
    """Minimum supported Python (X.Y) from [project].requires-python, e.g. '>=3.11,<3.13' -> '3.11'.

    `uv pip compile --universal` anchors its lower bound to the *target* Python, NOT to
    requires-python: compiling under 3.12 silently drops every 3.11-only pin (and its
    `; python_full_version < '3.12'` markers). Targeting the project floor makes the freeze cover the
    full supported range regardless of which interpreter runs the compile, so dev and CI agree.
    """
    data = tomllib.loads((PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    requires = data['project'].get('requires-python', '')
    m = re.search(r'>=\s*(\d+\.\d+)', requires)
    if not m:
        sys.exit(f"xx-constraints: cannot derive a Python floor from requires-python={requires!r}; "
                 f"expected a '>=X.Y' lower bound.")
    return m.group(1)


def compile_() -> int:
    """Recompile constraints.txt from all three pyprojects (siblings excluded from the output)."""
    siblings = _siblings()
    missing = [str(p) for p in siblings.values() if not p.is_file()]
    if missing:
        sys.exit(f'xx-constraints: sibling pyproject(s) not found: {", ".join(missing)}\n'
                 f'  the C++ siblings must be checked out (e.g. run `uv-sync py10x-core-dev`) so '
                 f'their third-party deps are frozen too.')
    # Exclude every first-party package (siblings + any workspace members) from the emitted freeze,
    # mirroring check()'s _first_party() set. The root project is never self-emitted by uv.
    no_emit_names = sorted({*siblings, *_workspace_members()})
    no_emit = [arg for name in no_emit_names for arg in ('--no-emit-package', name)]
    cmd = ['uv', 'pip', 'compile',
           'pyproject.toml', *[str(p) for p in siblings.values()],
           '--universal', '--all-extras', *no_emit,
           # Target the project's min Python so the universal fork covers every supported version
           # (see _python_floor); otherwise the freeze depends on the interpreter running the compile.
           '--python-version', _python_floor(),
           # Stable, machine-independent header: the absolute sibling paths above would otherwise
           # leak into the autogenerated comment and churn the diff on every machine / CI runner.
           '--custom-compile-command', 'xx-constraints compile',
           '--quiet', '--upgrade','--output-file', str(CONSTRAINTS.name)]
    print('$', ' '.join(cmd))
    return subprocess.run(cmd, cwd=PROJECT_ROOT).returncode


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
        print('Regenerate with `xx-constraints compile` (in py10x-core-dev mode, with ../cxx10x up '
              'to date) and commit constraints.txt.')
        return 1
    print(f'xx-constraints check OK - all {len(installed) - len(exclude & set(installed))} '
          f'third-party distributions are pinned.')
    return 0


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'compile'
    if cmd == 'compile':
        sys.exit(compile_())
    if cmd == 'check':
        sys.exit(check())
    sys.exit('Usage: xx-constraints [compile|check]')


if __name__ == '__main__':
    main()
