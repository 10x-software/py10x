"""`xx-constraints` - generate / verify the committed third-party dependency freeze.

`constraints.txt` pins the *full third-party transitive graph* of py10x-core **and** its C++ siblings
(py10x-kernel / py10x-infra), so dev and CI installs are reproducible. It is applied via
`uv pip install -c constraints.txt` on every install (see `dev_10x/uv_sync.py` and the CI workflows).

The three first-party packages are deliberately NOT pinned here: py10x-core is the project root (uv
never self-emits it; its test-group reverse dep is a PEP 735 group, not pulled by `uv pip compile`),
and the siblings are `--no-emit`'d. Their versions are owned by the sibling-source profiles and the
xx-promote pin model, not by this freeze.

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
# Owned by the profile system / xx-promote, never by this freeze.
FIRST_PARTY = ('py10x-core', 'py10x-kernel', 'py10x-infra')


def _normalize(name: str) -> str:
    """PEP 503 normalized distribution name."""
    return re.sub(r'[-_.]+', '-', name).lower()


def _siblings() -> dict[str, Path]:
    """{dist-name: pyproject.toml path} for each [tool.dev_10x.siblings] entry."""
    data = tomllib.loads((PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    sibs = data.get('tool', {}).get('dev_10x', {}).get('siblings', {})
    return {name: (PROJECT_ROOT / spec['path'] / 'pyproject.toml') for name, spec in sibs.items()}


def compile_() -> int:
    """Recompile constraints.txt from all three pyprojects (siblings excluded from the output)."""
    siblings = _siblings()
    missing = [str(p) for p in siblings.values() if not p.is_file()]
    if missing:
        sys.exit(f'xx-constraints: sibling pyproject(s) not found: {", ".join(missing)}\n'
                 f'  the C++ siblings must be checked out (e.g. run `uv-sync py10x-core-dev`) so '
                 f'their third-party deps are frozen too.')
    no_emit = [arg for name in siblings for arg in ('--no-emit-package', name)]
    cmd = ['uv', 'pip', 'compile',
           'pyproject.toml', *[str(p) for p in siblings.values()],
           '--universal', '--all-extras', *no_emit,
           '--quiet', '-o', str(CONSTRAINTS.name)]
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
    exclude = {_normalize(n) for n in FIRST_PARTY}
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
