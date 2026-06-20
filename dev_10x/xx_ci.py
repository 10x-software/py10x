"""Dependency-light CI helpers for the pre-publish release gate.

Deliberately imports only `dev_10x.xx_helpers` (which needs just `packaging` + `tomlkit`) and
*not* `core_10x` - because `core_10x/__init__.py` imports the compiled `py10x_kernel`, and the
whole point of the gate is to run *before* a sibling is installed, to decide which sibling tag to
install. So `xx-promote` (built on `core_10x.traitable_cli`) cannot bootstrap py10x-core's own CI;
this module can. Run it without installing the project:

    uv run --no-project --with packaging --with tomlkit python -m dev_10x.xx_ci <command> ...

Commands (run from the py10x repo root):
    latest_tag <sibling>        print the sibling git tag matching its pinned spec in pyproject.toml
    verify_sibling <sibling>    after install: import the module and assert its installed version
                                equals the tag's version (catches stale wheels / scm drift)
"""
from __future__ import annotations

import importlib
import sys
from importlib.metadata import PackageNotFoundError, version as dist_version
from pathlib import Path

import tomlkit
from packaging.version import Version

from dev_10x.xx_helpers import GitHelpers, PyProjectHelpers, VersionHelpers


def _sibling(base: Path, name: str) -> tuple[Path, str]:
    """(repo root, tag prefix) for sibling `name`, read from `[tool.dev_10x.siblings]`."""
    doc = tomlkit.parse((base / "pyproject.toml").read_text(encoding="utf-8"))
    siblings = doc.get("tool", {}).get("dev_10x", {}).get("siblings", {})
    if name not in siblings:
        raise SystemExit(f"{name!r} not in [tool.dev_10x.siblings] of {base}/pyproject.toml")
    spec = siblings[name]
    src = (base / spec["path"]).resolve()
    prefix = spec.get("tag_prefix", f"{name}-v")
    return GitHelpers.git_root(src), prefix


def latest_tag(base: Path, name: str) -> str:
    """The sibling tag whose version satisfies the spec currently pinned for it in pyproject.toml.

    On an rc-tagged commit the prerelease-admitting dev pin selects the latest rc; on a release branch the
    final-only pin selects the latest final - i.e. exactly what the wheel being built will require.
    """
    repo, prefix = _sibling(base, name)
    spec = PyProjectHelpers.dependency_spec(base / "pyproject.toml", name)
    parsed = VersionHelpers.parse_pkg_tags(GitHelpers.list_tags(repo, f"{prefix}*"), prefix)
    tag = VersionHelpers.latest_matching_tag(parsed, spec)
    if tag is None:
        raise SystemExit(f"no {name} tag matches its pinned spec {spec!r}")
    return tag


def verify_sibling(base: Path, name: str) -> None:
    """Assert the installed sibling matches the tag we resolved: import it + compare versions."""
    repo, prefix = _sibling(base, name)
    expected = latest_tag(base, name)[len(prefix):]
    try:
        installed = dist_version(name)
    except PackageNotFoundError:
        raise SystemExit(f"{name} is not installed")
    if Version(installed) != Version(expected):
        raise SystemExit(f"{name}: installed {installed} != expected {expected} (from its pinned tag)")
    # Also import the compiled extension so a wheel that resolves but won't load fails the gate.
    importlib.import_module(name.replace("-", "_"))
    print(f"{name} {installed} OK")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        raise SystemExit(__doc__)
    cmd, *rest = argv
    base = Path.cwd()
    if cmd == "latest_tag" and len(rest) == 1:
        print(latest_tag(base, rest[0]))
    elif cmd == "verify_sibling" and len(rest) == 1:
        verify_sibling(base, rest[0])
    else:
        raise SystemExit(f"usage:\n{__doc__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
