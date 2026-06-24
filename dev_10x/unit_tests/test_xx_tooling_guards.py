"""Assumption guards over *external tooling* for the rc-branch-promotion design.

Unlike `test_xx_utils.py`'s pure PEP 440 guards (which lock `packaging` set-math) and unlike the
e2e tests (which check our own `xx-promote` logic), these lock the behavior of the *tools* the design
is built on - setuptools-scm/hatch-vcs version stamping, the git plumbing the reachability guard
relies on, and uv's resolver. If a future setuptools-scm / git / uv release changes that behavior,
these fail loudly before any release is mis-stamped or mis-resolved.

They invoke the real tools against throwaway repos / package indexes under `tmp_path`, so each is
skipped when its tool is unavailable. See `dev_10x/docs/rc-branch-promotion.md`
(Risks -> setuptools-scm correctness; Conscious tradeoffs -> reverse `>=` self-correcting).
"""
from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest
import setuptools_scm

from dev_10x.xx_helpers import GitHelpers

if TYPE_CHECKING:
    from pathlib import Path

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
requires_uv = pytest.mark.skipif(shutil.which("uv") is None, reason="uv not available")

# The exact git_describe_command the cxx10x siblings configure in `[tool.setuptools_scm]`
# (`../cxx10x/core_10x/pyproject.toml`); the `--match` glob is what scopes describe to this package.
SIBLING_DESCRIBE = "git describe --dirty --tags --long --match 'py10x-kernel-*' --abbrev=40"


def _init_repo(path: Path, branch: str = "main") -> Path:
    """A fresh git repo with identity configured (mirrors `test_xx_utils.test_tree_changed_since_tag`)."""
    path.mkdir(parents=True, exist_ok=True)
    GitHelpers.git(path, "init", "-q", "-b", branch)
    GitHelpers.git(path, "config", "user.email", "test@example.com")
    GitHelpers.git(path, "config", "user.name", "Test")
    return path


def _commit(repo: Path, name: str = "a.txt", content: str = "x\n", msg: str = "c") -> str:
    (repo / name).write_text(content, encoding="utf-8")
    GitHelpers.git(repo, "add", ".")
    GitHelpers.git(repo, "commit", "-qm", msg)
    return GitHelpers.git(repo, "rev-parse", "HEAD")


def _exit_code(repo: Path, *args: str) -> int:
    """Raw git exit code (GitHelpers.git hides it; the reachability gate keys off 0 vs 1)."""
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True).returncode


# --------------------------------------------------------------- #1 setuptools-scm version stamping
# Locks "tag on the committed HEAD with a clean, non-shallow tree stamps the tag version; dirty /
# shallow fall back to a dev version" - the assumption the whole release model rests on, and the
# traps README "setuptools-scm / hatch-vcs gotchas" enumerates.
@requires_git
def test_scm_core_default_config_stamps_tag_version(tmp_path):
    """core uses hatch-vcs (setuptools-scm default tag matching, prefix `v`): `v0.2.1` -> `0.2.1`."""
    repo = _init_repo(tmp_path / "core")
    _commit(repo)
    GitHelpers.git(repo, "tag", "v0.2.1")
    assert setuptools_scm.get_version(root=str(repo)) == "0.2.1"


@requires_git
def test_scm_sibling_match_glob_is_load_bearing(tmp_path):
    """sibling config selects only its own tag: a `py10x-infra-*` tag must NOT leak into the kernel version."""
    repo = _init_repo(tmp_path / "sib")
    _commit(repo)
    GitHelpers.git(repo, "tag", "py10x-kernel-v0.2.1")
    GitHelpers.git(repo, "tag", "py10x-infra-v9.9.9")  # higher, but excluded by the kernel match glob
    assert setuptools_scm.get_version(root=str(repo), git_describe_command=SIBLING_DESCRIBE) == "0.2.1"


@requires_git
def test_scm_dirty_tree_falls_back_to_dev_not_bare_tag(tmp_path):
    """An uncommitted edit must yield a guess-next-dev version, never the bare tag (the "dirty -> wrong version" trap)."""
    repo = _init_repo(tmp_path / "dirty")
    _commit(repo)
    GitHelpers.git(repo, "tag", "py10x-kernel-v0.2.1")
    (repo / "a.txt").write_text("changed\n", encoding="utf-8")  # tracked, uncommitted -> dirty tree
    v = setuptools_scm.get_version(root=str(repo), git_describe_command=SIBLING_DESCRIBE)
    assert v != "0.2.1"
    assert ".dev" in v


@requires_git
def test_scm_shallow_checkout_falls_back_absolutely(tmp_path):
    """A shallow checkout that prunes the tag commit degrades to the `0.1.dev…` no-tag fallback.

    This is the README "`0.1.dev1+g…` = NO tag found -> needs `fetch-depth: 0`" trap: with HEAD a
    commit past the tag, `--depth 1` drops the tag, so describe finds nothing.
    """
    repo = _init_repo(tmp_path / "full")
    _commit(repo, msg="c1")
    GitHelpers.git(repo, "tag", "py10x-kernel-v0.2.1")
    _commit(repo, content="x\ny\n", msg="c2")  # HEAD is now past the tagged commit
    shallow = tmp_path / "shallow"
    GitHelpers.git(tmp_path, "clone", "-q", "--depth", "1", f"file://{repo}", str(shallow))
    assert GitHelpers.list_tags(shallow, "*") == []  # the tag was pruned by the shallow clone
    v = setuptools_scm.get_version(root=str(shallow), git_describe_command=SIBLING_DESCRIBE)
    assert v.startswith("0.1.dev")


# --------------------------------------------------------------- #3 git plumbing the Guard relies on
# Stage-1 primitives only (Stage 2 markers/CAS excluded): locks that git's exit codes / pointer
# semantics match what the reachability guard and branch update assume.
@requires_git
def test_merge_base_is_ancestor_gates_from_main(tmp_path):
    """`git merge-base --is-ancestor main HEAD`: 0 when at/ahead of main, 1 when diverged behind it."""
    repo = _init_repo(tmp_path / "r")
    _commit(repo, msg="c1")
    assert _exit_code(repo, "merge-base", "--is-ancestor", "main", "HEAD") == 0  # HEAD == main
    GitHelpers.git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, name="f.txt", msg="feat")           # feature gains its own commit
    GitHelpers.git(repo, "checkout", "-q", "main")
    _commit(repo, name="m.txt", msg="main2")          # main advances independently -> diverged
    GitHelpers.git(repo, "checkout", "-q", "feature")
    assert _exit_code(repo, "merge-base", "--is-ancestor", "main", "HEAD") == 1  # main tip unreachable


@requires_git
def test_branch_force_reset_moves_pointer(tmp_path):
    """`git branch -f` force-resets a pointer to an unrelated commit (the `pre`/`prod` re-cut on --from=main)."""
    repo = _init_repo(tmp_path / "r")
    c1 = _commit(repo, msg="c1")
    c2 = _commit(repo, content="x\ny\n", msg="c2")
    GitHelpers.git(repo, "branch", "pre", c1)
    assert GitHelpers.git(repo, "rev-parse", "pre") == c1
    GitHelpers.git(repo, "branch", "-f", "pre", c2)
    assert GitHelpers.git(repo, "rev-parse", "pre") == c2


@requires_git
def test_fast_forward_detectable_via_is_ancestor(tmp_path):
    """The --from=release ff path: the old tip is an ancestor of the new (ff) but not of an unrelated line."""
    repo = _init_repo(tmp_path / "r")
    c1 = _commit(repo, msg="c1")
    GitHelpers.git(repo, "branch", "pre", c1)
    _commit(repo, content="x\ny\n", msg="c2")            # main moves forward linearly
    assert _exit_code(repo, "merge-base", "--is-ancestor", "pre", "HEAD") == 0  # ff is valid
    GitHelpers.git(repo, "checkout", "-q", "--orphan", "ortho")
    o = _commit(repo, name="o.txt", msg="orphan")        # an unrelated root
    assert _exit_code(repo, "merge-base", "--is-ancestor", "pre", o) == 1       # not a ff


@requires_git
def test_tag_at_commit_resolves_back(tmp_path):
    """`git tag <t> <commit>` tags a non-HEAD commit; `tag_commit` (rev-list -n1) resolves it back."""
    repo = _init_repo(tmp_path / "r")
    c1 = _commit(repo, msg="c1")
    _commit(repo, content="x\ny\n", msg="c2")
    GitHelpers.git(repo, "tag", "py10x-kernel-v0.2.1rc1", c1)
    assert GitHelpers.tag_commit(repo, "py10x-kernel-v0.2.1rc1") == c1


# ------------------------------------------------------------- #2 uv resolver backtracking (real uv)
# Locks the live half of "reverse `>=` is self-correcting via the forward `==`": the floor admits a
# too-new core, but core's exact `==` cross-pin makes the resolver backtrack to the coordinated one
# rather than hard-erroring. The PEP 440 intersection half is guarded in test_xx_utils.py.
_HATCH_PYPROJECT = """\
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{name}"
version = "{version}"
{deps_line}

[tool.hatch.build.targets.wheel]
packages = ["src/pkg"]
"""


def _build_wheel(workdir: Path, find_links: Path, name: str, version: str, deps: tuple = ()) -> None:
    """Build a minimal real wheel for `{name}=={version}` into `find_links` (real metadata, no stubs)."""
    src = workdir / f"{name}-{version}"
    (src / "src" / "pkg").mkdir(parents=True)
    (src / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    deps_line = f"dependencies = {list(deps)!r}" if deps else ""
    (src / "pyproject.toml").write_text(
        _HATCH_PYPROJECT.format(name=name, version=version, deps_line=deps_line), encoding="utf-8")
    subprocess.run(["uv", "build", "--wheel", "-q", "-o", str(find_links)],
                   cwd=src, check=True, capture_output=True, text=True)


@requires_uv
def test_reverse_floor_backtracks_to_coordinated_core(tmp_path):
    fl = tmp_path / "fl"
    fl.mkdir()
    work = tmp_path / "src"
    work.mkdir()
    _build_wheel(work, fl, "tenx-kernel", "1.4.0")
    _build_wheel(work, fl, "tenx-kernel", "1.4.1")  # the "too-new" the floor alone would pick
    _build_wheel(work, fl, "tenx-core", "1.4.0", deps=("tenx-kernel==1.4.0",))  # forward exact pin

    def resolve(reqs: str) -> str:
        proc = subprocess.run(
            ["uv", "pip", "compile", "-", "--find-links", str(fl), "--no-index",
             "--no-annotate", "--no-header"],
            input=reqs, cwd=tmp_path, capture_output=True, text=True, check=True)
        return proc.stdout

    # Control: the reverse floor on its own admits (and picks) the newer kernel.
    assert "tenx-kernel==1.4.1" in resolve("tenx-kernel>=1.4.0\n")
    # With core present, its exact `==` pulls the floor back to the coordinated 1.4.0 - the resolver
    # backtracks rather than erroring.
    out = resolve("tenx-core\ntenx-kernel>=1.4.0\n")
    assert "tenx-kernel==1.4.0" in out
    assert "tenx-kernel==1.4.1" not in out
