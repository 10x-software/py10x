"""`xx-constraints` - generate / verify the committed third-party dependency freeze.

`constraints.txt` pins the *full third-party transitive graph* of py10x-core **and** its C++ siblings
(py10x-kernel / py10x-infra), so dev and CI installs are reproducible. It is applied via
`uv pip install -c constraints.txt` on every install (see `dev_10x/uv_sync.py` and the CI workflows).

First-party packages are deliberately NOT pinned here. Compile `--no-emit`'s `_first_party()`: root,
siblings, downstreams, and `[tool.uv.workspace]` members from the repo root **and** from each
sibling/downstream packaging root (e.g. fin-base's `cxxfin` → `py10x-fin-base-cxx`). Their versions
stay owned by editable/git/promote pins, not this freeze.

Subcommands:
  compile [--upgrade] [--with-downstream [name…]]
           regenerate constraints.txt from py10x's + siblings' pyproject.toml.
           Downstream packaging roots are **opt-in** (same flag shape as `uv-sync`), matching
           default core isolation — fin-base's third-party graph is not in the default freeze.
           Without --upgrade: conservative regen (keeps existing pins where still valid).
           With --upgrade: bump every pin to the latest version allowed by the ranges.
           Needs the ../cxx10x checkout (a precondition of `uv-sync py10x-core-dev`).
  check    assert every *installed* third-party distribution is pinned in constraints.txt

Kernel-free (subprocess + importlib.metadata only) so it runs before any sibling is built.
"""

from __future__ import annotations

import importlib.metadata as md
import re
import subprocess
import sys
from pathlib import Path

import tomllib

from dev_10x.uv_sync import _parse_with_downstream

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


def _compile_inputs(
    with_downstream: bool = False,
    downstream_filter: set[str] | None = None,
) -> dict[str, Path]:
    """pyproject paths fed to `uv pip compile` (siblings; downstreams only if opted in)."""
    inputs = dict(_siblings())
    if not with_downstream:
        return inputs
    ds = _downstreams()
    if downstream_filter is not None:
        unknown = sorted(downstream_filter - set(ds))
        if unknown:
            sys.exit(f'xx-constraints: unknown downstream(s): {", ".join(unknown)}\n  configured: {", ".join(sorted(ds)) or "(none)"}')
        ds = {n: p for n, p in ds.items() if n in downstream_filter}
    inputs.update(ds)
    return inputs


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
        sys.exit(f"xx-constraints: cannot derive a Python floor from requires-python={requires!r}; expected a '>=X.Y' lower bound.")
    return m.group(1)


def compile_(
    upgrade: bool = False,
    with_downstream: bool = False,
    downstream_filter: set[str] | None = None,
) -> int:
    """Recompile constraints.txt from core + siblings (+ opt-in downstream pyprojects)."""
    compile_inputs = _compile_inputs(with_downstream, downstream_filter)
    missing = [str(p) for p in compile_inputs.values() if not p.is_file()]
    if missing:
        sys.exit(
            f'xx-constraints: first-party pyproject(s) not found: {", ".join(missing)}\n'
            f'  siblings need the ../cxx10x checkout (e.g. `uv-sync py10x-core-dev`); '
            f'downstreams need their packaging roots present (and `--with-downstream`).'
        )
    # Exclude every first-party package from the emitted freeze (mirrors check()'s `_first_party()`).
    no_emit_names = sorted(_first_party())
    no_emit = [arg for name in no_emit_names for arg in ('--no-emit-package', name)]
    compile_cmd_parts = ['xx-constraints', 'compile']
    if with_downstream:
        compile_cmd_parts.append('--with-downstream')
        if downstream_filter:
            compile_cmd_parts.extend(sorted(downstream_filter))
    if upgrade:
        compile_cmd_parts.append('--upgrade')
    compile_cmd = ' '.join(compile_cmd_parts)
    cmd = [
        'uv',
        'pip',
        'compile',
        'pyproject.toml',
        *[str(p) for p in compile_inputs.values()],
        '--universal',
        '--all-extras',
        *no_emit,
        # Target the project's min Python so the universal fork covers every supported version
        # (see _python_floor); otherwise the freeze depends on the interpreter running the compile.
        '--python-version',
        _python_floor(),
        # Stable, machine-independent header: the absolute sibling paths above would otherwise
        # leak into the autogenerated comment and churn the diff on every machine / CI runner.
        '--custom-compile-command',
        compile_cmd,
        '--quiet',
    ]
    if upgrade:
        cmd.append('--upgrade')
    cmd.extend(['--output-file', str(CONSTRAINTS.name)])
    print('$', ' '.join(cmd))
    return subprocess.run(cmd, cwd=PROJECT_ROOT, check=False).returncode


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
        print('Regenerate with `xx-constraints compile` (in py10x-core-dev mode, with ../cxx10x up to date) and commit constraints.txt.')
        return 1
    print(f'xx-constraints check OK - all {len(installed) - len(exclude & set(installed))} third-party distributions are pinned.')
    return 0


def main() -> None:
    args = sys.argv[1:]
    if not args:
        sys.exit(compile_())
    cmd = args[0]
    if cmd == 'compile':
        with_downstream, downstream_filter, rest = _parse_with_downstream(tuple(args[1:]))
        sys.exit(
            compile_(
                upgrade='--upgrade' in rest,
                with_downstream=with_downstream,
                downstream_filter=downstream_filter,
            )
        )
    if cmd == 'check':
        sys.exit(check())
    sys.exit('Usage: xx-constraints [compile [--upgrade] [--with-downstream [name…]]|check]')


if __name__ == '__main__':
    main()
