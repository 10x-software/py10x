"""Dependency-light CI helpers for the pre-publish release gate.

Deliberately imports only `dev_10x.xx_helpers` (which needs just `packaging` + `tomlkit`) and
*not* `core_10x` - because `core_10x/__init__.py` imports the compiled `py10x_kernel`, and the
whole point of the gate is to run *before* a sibling is installed, to decide which sibling tag to
install. So `xx-promote` (built on `core_10x.traitable_cli`) cannot bootstrap py10x-core's own CI;
this module can. Bootstrap a venv first (same as publish CI / `build.yml`):

    uv venv
    uv pip install -c constraints.txt packaging tomlkit setuptools-scm
    python -m dev_10x.xx_ci <command> ...

Or for ad-hoc local use: `uv run --no-project --with packaging --with tomlkit --with setuptools-scm python -m dev_10x.xx_ci …`

Commands (run from the py10x repo root):
    latest_tag <sibling>              sibling git tag matching its pinned spec in pyproject.toml
    verify_sibling <sibling>          after install: import + assert installed version == tag
    sibling_branch_ready B            exit 0 when every sibling at origin/B satisfies its pin
    wait_sibling_branch_ready B [sync_base]
                                      poll until ready (env: WAIT_FOR_SIBLING_BRANCH_TIMEOUT,
                                      WAIT_FOR_SIBLING_BRANCH_INTERVAL); optional sync_base
                                      refreshes the py10x checkout each attempt (cxx10x CI)
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version as dist_version
from pathlib import Path

import tomlkit
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from dev_10x.xx_helpers import GitHelpers, PyProjectHelpers, VersionHelpers


@dataclass(frozen=True)
class SiblingCheck:
    name: str
    src_dir: Path
    pin: str


def _siblings_doc(base: Path) -> dict:
    doc = tomlkit.parse((base / "pyproject.toml").read_text(encoding="utf-8"))
    siblings = doc.get("tool", {}).get("dev_10x", {}).get("siblings", {})
    if not siblings:
        raise SystemExit(f"no [tool.dev_10x.siblings] in {base}/pyproject.toml")
    return siblings


def _sibling_checks(base: Path) -> list[SiblingCheck]:
    pyproject = base / "pyproject.toml"
    return [
        SiblingCheck(
            name=name,
            src_dir=(base / spec["path"]).resolve(),
            pin=PyProjectHelpers.dependency_spec(pyproject, name),
        )
        for name, spec in _siblings_doc(base).items()
    ]


def _sibling(base: Path, name: str) -> tuple[Path, str]:
    """(repo root, tag prefix) for sibling `name`, read from `[tool.dev_10x.siblings]`."""
    siblings = _siblings_doc(base)
    if name not in siblings:
        raise SystemExit(f"{name!r} not in [tool.dev_10x.siblings] of {base}/pyproject.toml")
    spec = siblings[name]
    src = (base / spec["path"]).resolve()
    prefix = spec.get("tag_prefix", f"{name}-v")
    return GitHelpers.git_root(src), prefix


def _scm_version(src_dir: Path) -> Version:
    ver = subprocess.check_output(
        [sys.executable, "-m", "setuptools_scm"],
        cwd=src_dir,
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()
    return Version(ver.split("+")[0])


def _sync_remote_branch(repo: Path, branch: str) -> None:
    if GitHelpers.has_origin(repo):
        GitHelpers.git(repo, "fetch", "--quiet", "--tags", "origin", branch)
        GitHelpers.git(repo, "pull", "--ff-only", "origin", branch)


def sibling_branch_ready(base: Path, branch: str = "main", *, verbose: bool = False) -> bool:
    """Return True when every sibling's setuptools-scm version satisfies its forward pin on `branch`.

    Siblings are read from `[tool.dev_10x.siblings]`; git fetch + pull --ff-only run once per
    distinct sibling repo root (multiple siblings may share one repo).
    """
    checks = _sibling_checks(base)
    for repo in {GitHelpers.git_root(check.src_dir) for check in checks}:
        _sync_remote_branch(repo, branch)

    ready = True
    for check in checks:
        try:
            ver = _scm_version(check.src_dir)
        except (subprocess.CalledProcessError, OSError, ValueError) as ex:
            ready = False
            if verbose:
                print(f"{check.name}: setuptools-scm failed ({ex})", file=sys.stderr)
            continue
        if ver not in SpecifierSet(check.pin):
            ready = False
            if verbose:
                print(f"{check.name}: {ver} does not satisfy {check.pin!r}", file=sys.stderr)
        elif verbose:
            print(f"{check.name}: {ver} satisfies {check.pin!r}")
    return ready


def wait_sibling_branch_ready(
    base: Path,
    branch: str = "main",
    *,
    sync_base: bool = False,
    timeout: float | None = None,
    interval: float | None = None,
    verbose: bool = False,
) -> int:
    """Poll ``sibling_branch_ready`` until success or timeout (exit 0 / 1)."""
    timeout = float(os.environ.get("WAIT_FOR_SIBLING_BRANCH_TIMEOUT", timeout if timeout is not None else 120))
    interval = float(os.environ.get("WAIT_FOR_SIBLING_BRANCH_INTERVAL", interval if interval is not None else 5))
    deadline = time.monotonic() + timeout
    while True:
        if sync_base:
            _sync_remote_branch(base, branch)
        if sibling_branch_ready(base, branch, verbose=verbose):
            return 0
        if time.monotonic() >= deadline:
            print(
                f"wait_sibling_branch_ready: timed out after {timeout}s (branch={branch})",
                file=sys.stderr,
            )
            return 1
        print(
            f"wait_sibling_branch_ready: not ready; retrying in {interval}s...",
            file=sys.stderr,
        )
        time.sleep(interval)


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


def verify_sibling(base: Path, name: str) -> int:
    """Assert the installed sibling matches the tag we resolved: import it + compare versions."""
    _, prefix = _sibling(base, name)
    expected = latest_tag(base, name)[len(prefix):]
    try:
        installed = dist_version(name)
    except PackageNotFoundError:
        raise SystemExit(f"{name} is not installed")
    if Version(installed) != Version(expected):
        raise SystemExit(f"{name}: installed {installed} != expected {expected} (from its pinned tag)")
    importlib.import_module(name.replace("-", "_"))
    print(f"{name} {installed} OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        raise SystemExit(__doc__)
    cmd = argv[0]
    base = Path.cwd()
    if cmd == "latest_tag" and len(argv) == 2:
        print(latest_tag(base, argv[1]))
        return 0
    if cmd == "verify_sibling" and len(argv) == 2:
        return verify_sibling(base, argv[1])
    if cmd == "sibling_branch_ready" and len(argv) == 2:
        return int(not sibling_branch_ready(base, argv[1]))
    if cmd == "wait_sibling_branch_ready" and 2 <= len(argv) <= 3:
        sync_base = len(argv) == 3
        if sync_base and argv[2] != "sync_base":
            raise SystemExit(f"usage:\n{__doc__}")
        return wait_sibling_branch_ready(base, argv[1], sync_base=sync_base)
    raise SystemExit(f"usage:\n{__doc__}")


if __name__ == "__main__":
    raise SystemExit(main())
