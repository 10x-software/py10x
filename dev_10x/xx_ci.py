"""Dependency-light CI helpers for the pre-publish release gate.

Deliberately imports only `dev_10x.xx_helpers` (which needs just `packaging` + `tomlkit`) and
*not* `core_10x` - because `core_10x/__init__.py` imports the compiled `py10x_kernel`, and the
whole point of the gate is to run *before* a sibling is installed, to decide which sibling tag to
install. So `xx-promote` (built on `core_10x.traitable_cli`) cannot bootstrap py10x-core's own CI;
this module can. Bootstrap via `uv run --no-project --with packaging --with tomlkit --with setuptools-scm`,
or set up the dev env first (`./xx-build init`).

Commands (run from the py10x repo root):
    latest_tag <sibling>              sibling git tag matching its pinned spec in pyproject.toml
    verify_sibling <sibling>          after install: import + assert installed version == tag
    wait_pypi_release VERSION         poll until this repo's own package (name from
                                      [project.name]) is at VERSION on PyPI, then its exact
                                      ==-pinned siblings (env: PYPI_TIMEOUT_SEC, PYPI_POLL_SEC)
    wait_pypi_release_for_wheel WHEEL same wait, but VERSION is read from WHEEL's own pin on this
                                      repo's package (e.g. a downstream wheel pinning py10x-core)
    wait_sibling_releases             poll until every sibling ==-pinned in this checkout's
                                      pyproject.toml is on PyPI (run before publishing core)
    downstream_build_constraints PYPROJECT OUT
                                      wait_pypi_release for the core version a downstream
                                      release commit's PYPROJECT ==-pins, then write that core's
                                      sibling pins to OUT as pip constraints
"""

from __future__ import annotations

import importlib
import os
import sys
import time
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as dist_version
from pathlib import Path

import tomlkit
from packaging.requirements import Requirement
from packaging.version import Version

from dev_10x.xx_helpers import GitHelpers, PyPIHelpers, PyProjectHelpers, VersionHelpers


def _siblings_doc(base: Path) -> dict:
    doc = tomlkit.parse((base / 'pyproject.toml').read_text(encoding='utf-8'))
    siblings = doc.get('tool', {}).get('dev_10x', {}).get('siblings', {})
    if not siblings:
        raise SystemExit(f'no [tool.dev_10x.siblings] in {base}/pyproject.toml')
    return siblings


def _sibling(base: Path, name: str) -> tuple[Path, str]:
    """(repo root, tag prefix) for sibling `name`, read from `[tool.dev_10x.siblings]`."""
    siblings = _siblings_doc(base)
    if name not in siblings:
        raise SystemExit(f'{name!r} not in [tool.dev_10x.siblings] of {base}/pyproject.toml')
    spec = siblings[name]
    src = (base / spec['path']).resolve()
    prefix = spec.get('tag_prefix', f'{name}-v')
    return GitHelpers.git_root(src), prefix


def wait_pypi_release(base: Path, version: str, *, timeout: float | None = None, poll: float | None = None) -> int:
    """Poll until this repo's own package (name from `[project.name]`) is at `version` on PyPI,
    then poll for each of its exact `==`-pinned first-party siblings (from
    `[tool.dev_10x.siblings]`, resolved via the published release's own `Requires-Dist` - so a
    sibling bump is picked up automatically, never hand-maintained here)."""
    name = PyProjectHelpers.project_name(base / 'pyproject.toml')
    siblings = set(_siblings_doc(base))
    deadline, poll = _pypi_deadline(timeout, poll)

    if not PyPIHelpers.wait_for_release(name, version, deadline, poll):
        return 1

    pins = PyPIHelpers.exact_pins(name, version, siblings)
    if not pins:
        print(f'wait_pypi_release: warning: no == pins for {sorted(siblings)} on {name}=={version}', file=sys.stderr)
    return _wait_for_pins(pins, deadline, poll)


def wait_sibling_releases(base: Path, *, timeout: float | None = None, poll: float | None = None) -> int:
    """Poll until every sibling this checkout `==`-pins is on PyPI. Run on a `pre`/`prod` release
    commit before publishing core, so core never reaches the index ahead of the siblings it pins."""
    siblings = set(_siblings_doc(base))
    pins = PyProjectHelpers.exact_pins_from_text((base / 'pyproject.toml').read_text(encoding='utf-8'), siblings)
    if not pins:
        raise SystemExit(f'no == pins for {sorted(siblings)} in {base}/pyproject.toml - not a release commit?')
    deadline, poll = _pypi_deadline(timeout, poll)
    return _wait_for_pins(pins, deadline, poll)


def _pypi_deadline(timeout: float | None, poll: float | None) -> tuple[float, float]:
    timeout = float(os.environ.get('PYPI_TIMEOUT_SEC', timeout if timeout is not None else 1800))
    poll = float(os.environ.get('PYPI_POLL_SEC', poll if poll is not None else 90))
    return time.monotonic() + timeout, poll


def _wait_for_pins(pins: dict[str, str], deadline: float, poll: float) -> int:
    for name, version in pins.items():
        if not PyPIHelpers.wait_for_release(name, version, deadline, poll):
            return 1
    return 0


def _project_pin_from_wheel(wheel: Path, name: str) -> str:
    """Exact `==` pin for `name` in a built wheel's `Requires-Dist` metadata."""
    from email.parser import Parser
    from zipfile import ZipFile

    with ZipFile(wheel) as zf:
        meta_names = [n for n in zf.namelist() if n.endswith('.dist-info/METADATA')]
        if not meta_names:
            raise SystemExit(f'no METADATA in {wheel}')
        meta = Parser().parsestr(zf.read(meta_names[0]).decode())
    for req_str in (v for k, v in meta.items() if k.lower() == 'requires-dist'):
        try:
            req = Requirement(req_str.split(';', 1)[0].strip())
        except Exception:  # noqa: BLE001, S112 - a malformed Requires-Dist entry is skipped, not fatal
            continue
        if req.name == name:
            exact = [s.version for s in req.specifier if s.operator == '==']
            if exact:
                return exact[0]
    raise SystemExit(f'{wheel}: no exact {name}== pin in Requires-Dist')


def wait_pypi_release_for_wheel(base: Path, wheel: Path, *, timeout: float | None = None, poll: float | None = None) -> int:
    """Read this repo's own package's exact pin out of `wheel`'s metadata (e.g. a downstream
    fin-base wheel pinning py10x-core), then `wait_pypi_release` for it and its siblings."""
    name = PyProjectHelpers.project_name(base / 'pyproject.toml')
    version = _project_pin_from_wheel(wheel, name)
    print(f'{wheel.name} pins {name}=={version}', flush=True)
    return wait_pypi_release(base, version, timeout=timeout, poll=poll)


def downstream_build_constraints(base: Path, pyproject: Path, out: Path, *, timeout: float | None = None, poll: float | None = None) -> int:
    """Write the siblings coordinated with a downstream release (e.g. `py10x-kernel==X`) to `out` as
    pip constraints, once they are on PyPI. A downstream C++ extension (cxxfin) builds in isolation
    against whatever kernel pip resolves; it must be the coordinated one, as pybind11 types do not
    cross kernels built with different pybind11 internals."""
    name = PyProjectHelpers.project_name(base / 'pyproject.toml')
    version = PyProjectHelpers.exact_pins_from_text(pyproject.read_text(encoding='utf-8'), {name}).get(name)
    if version is None:
        raise SystemExit(f'no {name}== pin in {pyproject} - not a release commit?')
    if rc := wait_pypi_release(base, version, timeout=timeout, poll=poll):
        return rc
    pins = PyPIHelpers.exact_pins(name, version, set(_siblings_doc(base)))
    if not pins:
        raise SystemExit(f'no == sibling pins on {name}=={version}')
    out.write_text(''.join(f'{n}=={v}\n' for n, v in sorted(pins.items())), encoding='utf-8')
    print(f'{out}: {", ".join(f"{n}=={v}" for n, v in sorted(pins.items()))}', flush=True)
    return 0


def latest_tag(base: Path, name: str) -> str:
    """The sibling tag whose version satisfies the spec currently pinned for it in pyproject.toml.

    On an rc-tagged commit the prerelease-admitting dev pin selects the latest rc; on a release branch the
    final-only pin selects the latest final - i.e. exactly what the wheel being built will require.
    """
    repo, prefix = _sibling(base, name)
    spec = PyProjectHelpers.dependency_spec(base / 'pyproject.toml', name)
    parsed = VersionHelpers.parse_pkg_tags(GitHelpers.list_tags(repo, f'{prefix}*'), prefix)
    tag = VersionHelpers.latest_matching_tag(parsed, spec)
    if tag is None:
        raise SystemExit(f'no {name} tag matches its pinned spec {spec!r}')
    return tag


def verify_sibling(base: Path, name: str) -> int:
    """Assert the installed sibling matches the tag we resolved: import it + compare versions."""
    _, prefix = _sibling(base, name)
    expected = latest_tag(base, name)[len(prefix) :]
    try:
        installed = dist_version(name)
    except PackageNotFoundError as e:
        raise SystemExit(f'{name} is not installed') from e
    if Version(installed) != Version(expected):
        raise SystemExit(f'{name}: installed {installed} != expected {expected} (from its pinned tag)')
    importlib.import_module(name.replace('-', '_'))
    print(f'{name} {installed} OK')
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        raise SystemExit(__doc__)
    cmd = argv[0]
    base = Path.cwd()
    if cmd == 'latest_tag' and len(argv) == 2:
        print(latest_tag(base, argv[1]))
        return 0
    if cmd == 'verify_sibling' and len(argv) == 2:
        return verify_sibling(base, argv[1])
    if cmd == 'wait_pypi_release' and len(argv) == 2:
        return wait_pypi_release(base, argv[1])
    if cmd == 'wait_sibling_releases' and len(argv) == 1:
        return wait_sibling_releases(base)
    if cmd == 'wait_pypi_release_for_wheel' and len(argv) == 2:
        return wait_pypi_release_for_wheel(base, Path(argv[1]))
    if cmd == 'downstream_build_constraints' and len(argv) == 3:
        return downstream_build_constraints(base, Path(argv[1]), Path(argv[2]))
    raise SystemExit(f'usage:\n{__doc__}')


if __name__ == '__main__':
    raise SystemExit(main())
