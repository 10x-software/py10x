"""Tests for `dev_10x.xx_ci` (kernel-free CI helpers)."""
from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
import tomlkit

from dev_10x import xx_ci
from dev_10x.xx_helpers import GitHelpers, VersionHelpers
from packaging.specifiers import SpecifierSet
from packaging.version import Version

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")

KERNEL = "py10x-kernel"
INFRA = "py10x-infra"


def _init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    GitHelpers.git(repo, "init", "-q", "-b", "main")
    GitHelpers.git(repo, "config", "user.email", "test@example.com")
    GitHelpers.git(repo, "config", "user.name", "Test")


def _write_pkg(src: Path, name: str) -> None:
    src.mkdir(parents=True, exist_ok=True)
    (src / "pkg").mkdir(exist_ok=True)
    (src / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    prefix = f"{name}-v"
    describe = (
        f"git describe --dirty --tags --long --match '{prefix}*' --abbrev=40"
    )
    (src / "pyproject.toml").write_text(
        "[project]\n"
        f'name = "{name}"\n'
        'dependencies = ["uuid6>=2025.0.1"]\n\n'
        "[build-system]\n"
        'requires = ["setuptools>=61", "setuptools-scm>=8"]\n'
        'build-backend = "setuptools.build_meta"\n\n'
        "[tool.setuptools.packages.find]\n"
        'where = ["."]\n'
        'include = ["pkg*"]\n\n'
        "[tool.setuptools_scm]\n"
        f'git_describe_command = "{describe}"\n'
        "search_parent_directories = true\n",
        encoding="utf-8",
    )


def _commit(repo: Path, msg: str = "init") -> str:
    GitHelpers.git(repo, "add", ".")
    GitHelpers.git(repo, "commit", "-qm", msg)
    return GitHelpers.git(repo, "rev-parse", "HEAD")


def _fixture_tree(tmp_path: Path, *, kernel_pin: str, infra_pin: str | None = None):
    """py10x + cxx10x with two sibling packages in one repo."""
    cxx = tmp_path / "cxx10x"
    py = tmp_path / "py10x"
    _init(cxx)
    _write_pkg(cxx / "core_10x", KERNEL)
    _write_pkg(cxx / "infra_10x", INFRA)
    _commit(cxx, "init cxx10x")

    infra_pin = infra_pin if infra_pin is not None else kernel_pin
    _init(py)
    (py / "pyproject.toml").write_text(tomlkit.dumps(tomlkit.parse(
        "[project]\n"
        'name = "py10x-core"\n'
        "dependencies = [\n"
        f'    "{KERNEL} ({kernel_pin})",\n'
        f'    "{INFRA} ({infra_pin})",\n'
        "]\n\n"
        "[tool.dev_10x.siblings]\n"
        f'{KERNEL} = {{ path = "../cxx10x/core_10x" }}\n'
        f'{INFRA} = {{ path = "../cxx10x/infra_10x" }}\n'
    )), encoding="utf-8")
    _commit(py, "init py10x")
    return py, cxx


def _tag_main_marker(cxx: Path, tag: str) -> None:
    GitHelpers.git(cxx, "tag", tag, "HEAD")


def test_sibling_checks_reads_pyproject(tmp_path):
    py, _ = _fixture_tree(tmp_path, kernel_pin=">=0.0.1rc1,<0.0.1rc2")
    checks = xx_ci._sibling_checks(py)
    assert {c.name for c in checks} == {KERNEL, INFRA}
    expected = SpecifierSet(">=0.0.1rc1,<0.0.1rc2")
    assert all(SpecifierSet(c.pin) == expected for c in checks)


def test_sibling_branch_ready_accepts_marker_line(tmp_path):
    py, cxx = _fixture_tree(tmp_path, kernel_pin=VersionHelpers.rc_window_pin("0.0.1rc1"))
    _tag_main_marker(cxx, f"{KERNEL}-v0.0.1rc2.dev")
    _tag_main_marker(cxx, f"{INFRA}-v0.0.1rc2.dev")
    assert xx_ci.sibling_branch_ready(py)


def test_sibling_branch_ready_rejects_stale_main(tmp_path):
    py, cxx = _fixture_tree(tmp_path, kernel_pin=VersionHelpers.rc_window_pin("0.0.1rc1"))
    _tag_main_marker(cxx, f"{KERNEL}-v0.0.1rc1.dev")
    _tag_main_marker(cxx, f"{INFRA}-v0.0.1rc1.dev")
    assert not xx_ci.sibling_branch_ready(py)


def test_sibling_branch_ready_syncs_each_repo_once(tmp_path):
    py, cxx = _fixture_tree(tmp_path, kernel_pin=VersionHelpers.rc_window_pin("0.0.1rc1"))
    _tag_main_marker(cxx, f"{KERNEL}-v0.0.1rc2.dev")
    _tag_main_marker(cxx, f"{INFRA}-v0.0.1rc2.dev")
    bare = tmp_path / "cxx10x.git"
    GitHelpers.git(tmp_path, "init", "--bare", "-q", str(bare))
    GitHelpers.git(cxx, "remote", "add", "origin", str(bare))
    GitHelpers.git(cxx, "push", "-q", "origin", "main", "--tags")
    calls: list[tuple[Path, tuple[str, ...]]] = []
    orig = GitHelpers.git

    def tracking(repo, *args, check=True):
        calls.append((repo, args))
        return orig(repo, *args, check=check)

    with patch.object(GitHelpers, "git", staticmethod(tracking)):
        assert xx_ci.sibling_branch_ready(py)
    sync = [c for c in calls if c[1][:2] == ("fetch", "--quiet") or c[1][0] == "pull"]
    repos = {c[0] for c in sync}
    assert repos == {cxx}
    assert sum(1 for c in calls if c[1][0] == "pull") == 1


def test_scm_version_matches_setuptools_scm(tmp_path):
    _, cxx = _fixture_tree(tmp_path, kernel_pin=">=0.0.1")
    _tag_main_marker(cxx, f"{KERNEL}-v0.0.1rc2.dev")
    src = cxx / "core_10x"
    expected = xx_ci._scm_version(src)
    assert expected in SpecifierSet(VersionHelpers.rc_window_pin("0.0.1rc1"))


def test_wait_sibling_branch_ready_succeeds_immediately(tmp_path):
    py, cxx = _fixture_tree(tmp_path, kernel_pin=VersionHelpers.rc_window_pin("0.0.1rc1"))
    _tag_main_marker(cxx, f"{KERNEL}-v0.0.1rc2.dev")
    _tag_main_marker(cxx, f"{INFRA}-v0.0.1rc2.dev")
    assert xx_ci.wait_sibling_branch_ready(py, timeout=1, interval=0.01) == 0


def test_wait_sibling_branch_ready_times_out(tmp_path):
    py, cxx = _fixture_tree(tmp_path, kernel_pin=VersionHelpers.rc_window_pin("0.0.1rc1"))
    _tag_main_marker(cxx, f"{KERNEL}-v0.0.1rc1.dev")
    _tag_main_marker(cxx, f"{INFRA}-v0.0.1rc1.dev")
    assert xx_ci.wait_sibling_branch_ready(py, timeout=0.1, interval=0.05) == 1


def test_wait_sync_base_refreshes_py10x(tmp_path):
    py, cxx = _fixture_tree(tmp_path, kernel_pin=VersionHelpers.rc_window_pin("0.0.1rc1"))
    _tag_main_marker(cxx, f"{KERNEL}-v0.0.1rc2.dev")
    _tag_main_marker(cxx, f"{INFRA}-v0.0.1rc2.dev")
    bare = tmp_path / "py10x.git"
    GitHelpers.git(tmp_path, "init", "--bare", "-q", str(bare))
    GitHelpers.git(py, "remote", "add", "origin", str(bare))
    GitHelpers.git(py, "push", "-q", "origin", "main")
    calls: list[tuple[Path, tuple[str, ...]]] = []
    orig = GitHelpers.git

    def tracking(repo, *args, check=True):
        calls.append((repo, args))
        return orig(repo, *args, check=check)

    with patch.object(GitHelpers, "git", staticmethod(tracking)):
        assert xx_ci.wait_sibling_branch_ready(py, sync_base=True, timeout=1, interval=0.01) == 0
    assert any(c[0] == py and c[1][:2] == ("fetch", "--quiet") for c in calls)
