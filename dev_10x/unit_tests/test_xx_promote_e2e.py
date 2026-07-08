"""End-to-end execution tests for `xx-promote` against real git repos under `tmp_path`.

A 2-repo / 3-package fixture mirrors production: a `py10x` repo (py10x-core) and a `cxx10x` repo
holding `core_10x` (py10x-kernel) and `infra_10x` (py10x-infra) with the right tag prefixes. The
plan-level combinatorics live in test_xx_plan.py; here we assert *real git state* after execution -
branch HEADs, tags, commit parentage, and the pyproject pins recorded at the tag.

See `dev_10x/README.md` (xx-promote).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import tomlkit
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

from dev_10x import xx_promote as xp
from dev_10x.xx_helpers import GitHelpers, VersionHelpers

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")

DEV_PIN = ">=0.2.0,<=0.2.1,!=0.2.1,>=0.0.0.dev0"   # a prerelease-admitting main dev pin


def _init(repo, branch="main"):
    repo.mkdir(parents=True, exist_ok=True)
    GitHelpers.git(repo, "init", "-q", "-b", branch)
    GitHelpers.git(repo, "config", "user.email", "test@example.com")
    GitHelpers.git(repo, "config", "user.name", "Test")


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repos(tmp_path):
    """Sibling `py10x` + `cxx10x` checkouts, each committed on `main`. Returns (py10x, cxx10x)."""
    cxx = tmp_path / "cxx10x"
    py = tmp_path / "py10x"

    _init(cxx)
    _write(cxx / "core_10x" / "pyproject.toml",
           '[project]\nname = "py10x-kernel"\ndependencies = ["uuid6>=2025.0.1"]\n')
    _write(cxx / "infra_10x" / "pyproject.toml",
           '[project]\nname = "py10x-infra"\ndependencies = ["uuid6>=2025.0.1"]\n')
    GitHelpers.git(cxx, "add", ".")
    GitHelpers.git(cxx, "commit", "-qm", "init cxx10x")

    _init(py)
    _write(py / "pyproject.toml", tomlkit.dumps(tomlkit.parse(
        '[project]\n'
        'name = "py10x-core"\n'
        'dependencies = [\n'
        f'    "py10x-kernel ({DEV_PIN})",\n'
        f'    "py10x-infra ({DEV_PIN})",\n'
        '    "numpy>=2.2.2,<2.5.0",\n'
        ']\n\n'
        '[tool.dev_10x.siblings]\n'
        'py10x-kernel = { path = "../cxx10x/core_10x" }\n'
        'py10x-infra = { path = "../cxx10x/infra_10x" }\n')))
    GitHelpers.git(py, "add", ".")
    GitHelpers.git(py, "commit", "-qm", "init py10x")
    return py, cxx


def _run_argv(argv):
    """Construct + run() the CLI (verify()/post_verify() preconditions, then apply, then push)."""
    rc, inst = xp.XxPromoteCli.instance_from_args(argv)
    assert rc, rc.error() if not rc else ""
    return inst.run()


def _run(cmd, py_repo, *flags):
    out = _run_argv([cmd, "--base", str(py_repo), *flags])
    assert out, out.error() if not out else ""
    return out


def _run_pre(py_repo, *flags):
    _run("pre", py_repo, *flags)


def _run_prod(py_repo, *flags):
    _run("prod", py_repo, *flags)


def _change_kernel_source(cxx, name):
    _write(cxx / "core_10x" / name, "x = 1\n")
    GitHelpers.git(cxx, "add", ".")
    GitHelpers.git(cxx, "commit", "-qm", f"kernel {name}")


def _dep_specs_at(repo, ref, rel_path):
    """{dep name: specifier str} from [project.dependencies] of `rel_path` at git `ref`."""
    doc = tomlkit.parse(GitHelpers.file_at_ref(repo, ref, rel_path))
    return {Requirement(str(e)).name: str(Requirement(str(e)).specifier)
            for e in doc["project"]["dependencies"]}


def _test_group_at(repo, ref, rel_path):
    doc = tomlkit.parse(GitHelpers.file_at_ref(repo, ref, rel_path))
    return list(doc.get("dependency-groups", {}).get("test", []))


def test_pre_from_main_cuts_coordinated_first_rc(repos):
    py, cxx = repos
    _run_pre(py)

    # --- core: pre branch + tag, with exact forward == pins on both siblings ---
    assert set(GitHelpers.list_tags(py, "v*")) == {"v0.0.1rc1", "v0.0.1rc2.dev"}
    assert GitHelpers.git(py, "rev-parse", "pre") == GitHelpers.tag_commit(py, "v0.0.1rc1")
    assert GitHelpers.tag_commit(py, "v0.0.1rc2.dev") == GitHelpers.git(py, "rev-parse", "main")
    core_deps = _dep_specs_at(py, "v0.0.1rc1", "pyproject.toml")
    assert core_deps["py10x-kernel"] == "==0.0.1rc1"
    assert core_deps["py10x-infra"] == "==0.0.1rc1"
    assert core_deps["numpy"] == "<2.5.0,>=2.2.2"            # untouched third-party dep

    # --- siblings: per-package pre branch + tag, with reverse >= test group on core ---
    for name, sub in (("py10x-kernel", "core_10x"), ("py10x-infra", "infra_10x")):
        tag = f"{name}-v0.0.1rc1"
        dev = f"{name}-v0.0.1rc2.dev"
        assert tag in GitHelpers.list_tags(cxx, f"{name}-v*")
        assert dev in GitHelpers.list_tags(cxx, f"{name}-v*")
        assert GitHelpers.git(cxx, "rev-parse", f"pre/{name}") == GitHelpers.tag_commit(cxx, tag)
        assert GitHelpers.tag_commit(cxx, dev) == GitHelpers.git(cxx, "merge-base", tag, "main")
        assert _test_group_at(cxx, tag, f"{sub}/pyproject.toml") == ["py10x-core>=0.0.1rc1"]

    # --- the cut forks from main and leaves main + the working tree untouched ---
    for repo in (py, cxx):
        assert GitHelpers.git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"
        assert GitHelpers.git(repo, "status", "--porcelain") == ""
    # pre forked from an earlier main commit; main then advanced with the rc-window epilogue
    fork = GitHelpers.git(py, "merge-base", "main", "pre")
    assert GitHelpers.is_ancestor(py, fork, "pre")
    # main epilogue: rc-window pins for the coordinated rc
    main_core = _dep_specs_at(py, "main", "pyproject.toml")
    assert SpecifierSet(main_core["py10x-kernel"]) == SpecifierSet(
        VersionHelpers.rc_window_pin("0.0.1rc1"))
    assert SpecifierSet(main_core["py10x-infra"]) == SpecifierSet(
        VersionHelpers.rc_window_pin("0.0.1rc1"))


def test_pre_dry_run_is_side_effect_free(repos):
    """`--dry-run` must mutate nothing - in particular no getter (evaluated on the verify path)
    may switch branches. Run from a non-`main` branch and assert HEAD and tags are untouched."""
    py, cxx = repos
    for repo in (py, cxx):
        GitHelpers.git(repo, "checkout", "-q", "-b", "feature")   # start off main
    _run_pre(py, "--dry-run")
    for repo in (py, cxx):
        assert GitHelpers.git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "feature"
        assert GitHelpers.list_tags(repo, "*") == []             # nothing cut
        assert GitHelpers.git(repo, "branch", "--list", "pre/*") == ""
        assert GitHelpers.git(repo, "status", "--porcelain") == ""


def test_pre_unchanged_packages_are_skipped(repos, capsys):
    """A second `pre` with no source changes re-cuts nothing and mints no new tags."""
    py, cxx = repos
    _run_pre(py)
    capsys.readouterr()  # discard first-run completion hints
    tags_py, tags_cxx = GitHelpers.list_tags(py, "*"), GitHelpers.list_tags(cxx, "*")
    _run_pre(py)                                            # nothing changed since the rc
    assert GitHelpers.list_tags(py, "*") == tags_py
    assert GitHelpers.list_tags(cxx, "*") == tags_cxx
    assert "Local changes applied" not in capsys.readouterr().out


def test_prod_stacks_final_on_rc_and_floors_main(repos):
    """prod promotes each rc: final stacked on the rc commit, exact `==` pins, main re-floored to dev."""
    py, cxx = repos
    _run_pre(py)               # rc1 across the board
    _run_prod(py)

    # --- core: prod branch + final tag, exact == on the released sibling finals ---
    assert "v0.0.1" in GitHelpers.list_tags(py, "v*")
    assert GitHelpers.git(py, "rev-parse", "prod") == GitHelpers.tag_commit(py, "v0.0.1")
    core_final = _dep_specs_at(py, "v0.0.1", "pyproject.toml")
    assert core_final["py10x-kernel"] == "==0.0.1"
    assert core_final["py10x-infra"] == "==0.0.1"
    # released source == rc source: the final commit is stacked directly on the rc commit
    assert GitHelpers.git(py, "rev-parse", "v0.0.1^") == GitHelpers.tag_commit(py, "v0.0.1rc1")

    # --- siblings: prod branch + final tag, reverse >= on the released core ---
    for name, sub in (("py10x-kernel", "core_10x"), ("py10x-infra", "infra_10x")):
        assert f"{name}-v0.0.1" in GitHelpers.list_tags(cxx, f"{name}-v*")
        assert GitHelpers.git(cxx, "rev-parse", f"prod/{name}") == GitHelpers.tag_commit(cxx, f"{name}-v0.0.1")
        assert _test_group_at(cxx, f"{name}-v0.0.1", f"{sub}/pyproject.toml") == ["py10x-core>=0.0.1"]

    # --- main epilogue: post-final window pins; reverse groups -> released core ---
    main_core = _dep_specs_at(py, "main", "pyproject.toml")
    assert SpecifierSet(main_core["py10x-kernel"]) == SpecifierSet(
        VersionHelpers.post_final_window_pin("0.0.1"))
    assert _test_group_at(cxx, "main", "core_10x/pyproject.toml") == ["py10x-core>=0.0.1"]
    for repo in (py, cxx):
        assert GitHelpers.git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"
        assert GitHelpers.git(repo, "status", "--porcelain") == ""

    # --- main dev markers: rc-line replaced with post-final `{next_micro}rc0.dev` above the release ---
    assert GitHelpers.list_tags(py, "v*") == ["v0.0.1", "v0.0.1rc1", "v0.0.2rc0.dev"]
    assert GitHelpers.list_tags(py, "pre/*") == ["pre/v0.0.1rc1"]
    assert GitHelpers.list_tags(py, "prod/*") == ["prod/v0.0.1"]
    for name in ("py10x-kernel", "py10x-infra"):
        tags = GitHelpers.list_tags(cxx, f"{name}-v*")
        assert f"{name}-v0.0.1" in tags and f"{name}-v0.0.1rc1" in tags
        assert f"{name}-v0.0.2rc0.dev" in tags
        assert f"{name}-v0.0.1rc2.dev" not in tags
    assert set(GitHelpers.list_tags(cxx, "pre/*")) == {
        "pre/py10x-kernel-v0.0.1rc1", "pre/py10x-infra-v0.0.1rc1"}
    assert set(GitHelpers.list_tags(cxx, "prod/*")) == {
        "prod/py10x-kernel-v0.0.1", "prod/py10x-infra-v0.0.1"}


def test_resync_does_not_print_promote_completion_hints(remotes, capsys):
    """resync resets local refs to origin — not an unpushed promote; no promote-style footer."""
    py, _cxx, _py_remote, _cxx_remote = remotes
    _run_pre(py)                                          # local-only cut gives resync something to reset
    capsys.readouterr()                                   # discard pre's promote footer
    _run_argv(["resync", "--base", str(py)])
    out = capsys.readouterr().out
    assert "reset-local" in out
    assert "Local changes applied" not in out
    assert "Refs pushed" not in out


def test_local_promote_work_requires_resync(remotes):
    """A promote run (even without --push) mutates main via the epilogue (pins + dev marker).
    A follow-up promote therefore fails require_synced on main (not just tags).
    Explicit resync is still the way to discard local work and get back to origin.
    (Pure tag-behind cases with matching main are now auto-reconciled by require_synced.)"""
    py, cxx, py_remote, _cxx_remote = remotes
    _run_pre(py)                                          # cut rc1 LOCALLY (no --push)
    assert "v0.0.1rc1" in GitHelpers.list_tags(py, "v*")
    assert GitHelpers.git(py_remote, "tag", "--list") == ""

    out = _run_argv(["pre", "--base", str(py), "--push"])
    assert not out and "origin/main" in (out.error() or "")   # main was advanced locally by the first promote

    _run("resync", py)                                   # discard local work (main + tags + branches)
    assert GitHelpers.list_tags(py, "v*") == [] and GitHelpers.list_tags(cxx, "py10x-kernel-v*") == []
    assert GitHelpers.git(py, "rev-parse", "--verify", "--quiet", "pre", check=False) == ""

    _run_pre(py, "--push")                               # now clean; succeeds and pushes
    assert "v0.0.1rc1" in GitHelpers.git(py_remote, "tag", "--list").split()


def test_partial_push_recovery_still_uses_resync(remotes):
    """Crash with siblings pushed but core not: the lagging repo has local main changes from the
    promote epilogue, so require_synced refuses on main. resync + re-run still works to resume
    (core re-cut to coordinate). Pure tag-only lag (main revs match) is handled by auto-reconcile
    inside require_synced."""
    py, cxx, py_remote, _cxx_remote = remotes
    _run_pre(py)                                          # cut rc1 everywhere, locally
    # simulate a crash mid-push: the siblings repo (cxx) got its atomic push, core (py) did not.
    GitHelpers.git(cxx, "push", "--atomic", "origin",
                   "+pre/py10x-kernel", "py10x-kernel-v0.0.1rc1",
                   "+pre/py10x-infra", "py10x-infra-v0.0.1rc1")

    out = _run_argv(["pre", "--base", str(py), "--push"])
    assert not out and "origin/main" in (out.error() or "")

    _run("resync", py)                                   # py back to origin (local promote work discarded)
    assert GitHelpers.list_tags(py, "v*") == []
    assert "py10x-kernel-v0.0.1rc1" in GitHelpers.list_tags(cxx, "py10x-kernel-v*")   # siblings intact

    _run_pre(py, "--push")                               # resumes: siblings skip, core re-cut + coordinated
    assert "v0.0.1rc1" in GitHelpers.git(py_remote, "tag", "--list").split()
    assert _dep_specs_at(py, "v0.0.1rc1", "pyproject.toml")["py10x-kernel"] == "==0.0.1rc1"
    assert GitHelpers.list_tags(py, "v*") == ["v0.0.1rc1", "v0.0.1rc2.dev"]


def test_pre_iterate_after_sibling_source_change_recoordinates(repos):
    """A kernel source change bumps kernel's rc and forces a core re-cut (pin lag); infra stays put."""
    py, cxx = repos
    _run_pre(py)                                           # rc1 across the board

    _change_kernel_source(cxx, "feature.py")               # real kernel source change on main
    _run_pre(py)

    assert "py10x-kernel-v0.0.1rc2" in GitHelpers.list_tags(cxx, "py10x-kernel-v*")
    assert "py10x-infra-v0.0.1rc2" not in GitHelpers.list_tags(cxx, "py10x-infra-v*")  # unchanged
    assert "v0.0.1rc2" in GitHelpers.list_tags(py, "v*")   # core forced to re-cut by the stale pin

    core_deps = _dep_specs_at(py, "v0.0.1rc2", "pyproject.toml")
    assert core_deps["py10x-kernel"] == "==0.0.1rc2"       # refreshed to the new kernel rc
    assert core_deps["py10x-infra"] == "==0.0.1rc1"        # infra unchanged -> its existing rc1
    # the new core rc forks from main, and the superseded rc1 survives only as its tag
    assert GitHelpers.git(py, "rev-parse", "pre") == GitHelpers.tag_commit(py, "v0.0.1rc2")
    assert GitHelpers.tag_commit(py, "v0.0.1rc1") != GitHelpers.tag_commit(py, "v0.0.1rc2")


def _run_yank(py_repo, pkg, version, *flags):
    _run("yank", py_repo, "--pkg", pkg, "--version", version, *flags)


def test_yank_latest_rc_rolls_pre_back_and_consumes_the_number(repos):
    """Yank the latest kernel rc: tag renamed, pre rolled back to the prior rc, number not reused."""
    py, cxx = repos
    _run_pre(py)                                # rc1
    _change_kernel_source(cxx, "feature.py")
    _run_pre(py)                                # kernel rc2 (+ core rc2)
    rc1_commit = GitHelpers.tag_commit(cxx, "py10x-kernel-v0.0.1rc1")

    _run_yank(py, "py10x-kernel", "0.0.1rc2")

    live = GitHelpers.list_tags(cxx, "py10x-kernel-v0.0.1rc2")          # plain tag gone
    assert "py10x-kernel-v0.0.1rc2" not in [t for t in live if not t.endswith("_yanked")]
    assert "py10x-kernel-v0.0.1rc3.dev" in GitHelpers.list_tags(cxx, "py10x-kernel-v*")  # dev marker kept
    assert "py10x-kernel-v0.0.1rc2_yanked" in GitHelpers.list_tags(cxx, "*")
    # pointer rollback: pre/py10x-kernel reconciled to the previous (live) rc
    assert GitHelpers.git(cxx, "rev-parse", "pre/py10x-kernel") == rc1_commit
    main_pins = _dep_specs_at(py, "main", "pyproject.toml")
    assert SpecifierSet(main_pins["py10x-kernel"]) == SpecifierSet(
        VersionHelpers.rc_window_pin("0.0.1rc1"))

    _change_kernel_source(cxx, "feature2.py")
    _run_pre(py)
    # the yanked rc2 number is consumed: the next kernel rc is rc3, never a reused rc2
    assert "py10x-kernel-v0.0.1rc3" in GitHelpers.list_tags(cxx, "py10x-kernel-v*")


def test_yank_non_latest_is_rejected_without_cascade(repos):
    """Stage 1 yanks the latest only; an older release is refused (cascade is Stage 2)."""
    py, cxx = repos
    _run_pre(py)
    _change_kernel_source(cxx, "feature.py")
    _run_pre(py)                                # kernel now at rc2
    # post_verify refuses an older release, returning a falsy RC (no throw).
    out = _run_argv(["yank", "--pkg", "py10x-kernel", "--version", "0.0.1rc1", "--base", str(py)])
    assert not out and "not the latest" in (out.error() or "")


@pytest.fixture
def remotes(tmp_path, repos):
    """Add bare `origin` remotes to both repos and seed `main`. Returns (py, cxx, py_remote, cxx_remote)."""
    py, cxx = repos
    py_remote, cxx_remote = tmp_path / "py10x.git", tmp_path / "cxx10x.git"
    for repo, remote in ((py, py_remote), (cxx, cxx_remote)):
        GitHelpers.git(tmp_path, "init", "--bare", "-q", str(remote))
        GitHelpers.git(repo, "remote", "add", "origin", str(remote))
        GitHelpers.git(repo, "push", "-q", "origin", "main")
    return py, cxx, py_remote, cxx_remote


def test_pre_push_lands_tags_and_force_resets_branches_on_remotes(remotes):
    py, _cxx, py_remote, cxx_remote = remotes

    _run_pre(py, "--push")

    # tags + branches landed on the bare remotes; publish triggers in separate pushes per package
    assert set(GitHelpers.git(py_remote, "tag", "--list").split()) == {
        "v0.0.1rc1", "v0.0.1rc2.dev", "pre/v0.0.1rc1"}
    assert sorted(GitHelpers.git(py_remote, "branch", "--list", "--format=%(refname:short)").split()) == ["main", "pre"]
    assert set(GitHelpers.git(cxx_remote, "branch", "--list", "--format=%(refname:short)").split()) == {
        "main", "pre/py10x-kernel", "pre/py10x-infra"}
    assert GitHelpers.git(py_remote, "rev-parse", "pre") == GitHelpers.tag_commit(py, "v0.0.1rc1")

    # a second cut force-resets the remote pre branch (non-ff) to the new rc. main must be pushed
    # first (the start invariant: local==remote), then the cut finishes with local==remote again.
    _write(py / "src.py", "x = 1\n")
    GitHelpers.git(py, "add", ".")
    GitHelpers.git(py, "commit", "-qm", "core change")
    GitHelpers.git(py, "push", "-q", "origin", "main")
    _run_pre(py, "--push")
    assert "v0.0.1rc2" in GitHelpers.git(py_remote, "tag", "--list").split()
    assert "pre/v0.0.1rc2" in GitHelpers.git(py_remote, "tag", "--list").split()
    assert "pre/v0.0.1rc1" not in GitHelpers.git(py_remote, "tag", "--list").split()
    assert GitHelpers.git(py_remote, "rev-parse", "pre") == GitHelpers.tag_commit(py, "v0.0.1rc2")
    # finish invariant: local == remote (tags + pre branch)
    assert set(GitHelpers.git(py, "tag", "--list").split()) == set(GitHelpers.git(py_remote, "tag", "--list").split())
    assert GitHelpers.git(py, "rev-parse", "pre") == GitHelpers.git(py_remote, "rev-parse", "pre")


def test_pre_pushes_each_publish_trigger_in_own_atomic_push(remotes, monkeypatch):
    """Publish-trigger creates are one push each; deletes never share a push with creates."""
    py, cxx, _py_remote, _cxx_remote = remotes
    trigger_create_pushes: list[tuple[Path, list[str]]] = []
    trigger_delete_pushes: list[tuple[Path, list[str]]] = []
    orig_git = GitHelpers.git

    def tracking_git(repo, *args, check=True):
        if args and args[0] == "push" and "--atomic" in args:
            refspecs = [a for a in args if a not in ("push", "--atomic", "origin", "-q")]
            if any(r.startswith("pre/") or r.startswith("prod/") for r in refspecs):
                trigger_create_pushes.append((repo, refspecs))
            elif any("refs/tags/pre/" in r or "refs/tags/prod/" in r for r in refspecs):
                trigger_delete_pushes.append((repo, refspecs))
        return orig_git(repo, *args, check=check)

    monkeypatch.setattr(GitHelpers, "git", staticmethod(tracking_git))
    _run_pre(py, "--push")

    assert not trigger_delete_pushes  # first cut: no prior publish triggers
    assert len(trigger_create_pushes) == 3  # core + kernel + infra
    assert len([specs for repo, specs in trigger_create_pushes if repo == cxx]) == 2
    for _repo, refspecs in trigger_create_pushes:
        assert sum(r.startswith("pre/") or r.startswith("prod/") for r in refspecs) == 1
        assert not any(r.startswith(":refs/") for r in refspecs)


def _delete_remote_triggers(repo, flavor: str):
    for tag in GitHelpers.ls_remote_tags(repo, f"{flavor}/*"):
        GitHelpers.git(repo, "push", "--atomic", "origin", f":refs/tags/{tag}")


def test_pre_publish_recreates_triggers_after_resync(remotes):
    """Crash recovery: resync drops local-only triggers, then `pre --publish-only --push` recreates them."""
    py, cxx, py_remote, cxx_remote = remotes
    _run_pre(py, "--push")
    for repo in (py, cxx):
        _delete_remote_triggers(repo, "pre")
    _run("resync", py)
    out = _run_argv(["pre", "--publish-only", "--base", str(py), "--push"])
    assert out, out.error() if not out else ""
    for remote in (py_remote, cxx_remote):
        triggers = [t for t in GitHelpers.git(remote, "tag", "--list").split() if t.startswith("pre/")]
        assert triggers


def test_pre_publish_refuses_existing_triggers(remotes, capsys):
    py, _cxx, _py_remote, _cxx_remote = remotes
    _run_pre(py, "--push")
    out = _run_argv(["pre", "--publish-only", "--base", str(py), "--push"])
    assert out, out.error() if not out else ""
    assert "already present" in capsys.readouterr().out


def test_pre_no_publish_then_publish_only(remotes):
    """Cut and push without triggers, then attach triggers in a second step."""
    py, _cxx, py_remote, _cxx_remote = remotes
    _run_pre(py, "--push", "--no-publish")
    assert not any(t.startswith("pre/") for t in GitHelpers.git(py_remote, "tag", "--list").split())
    assert "v0.0.1rc1" in GitHelpers.git(py_remote, "tag", "--list").split()
    _run_argv(["pre", "--publish-only", "--base", str(py), "--push"])
    assert "pre/v0.0.1rc1" in GitHelpers.git(py_remote, "tag", "--list").split()


def test_promote_refuses_unsynced_main(remotes):
    """Start invariant: an un-pushed `main` is refused (local != origin/main) and nothing is cut."""
    py, _cxx, py_remote, _cxx_remote = remotes
    _write(py / "src.py", "x = 1\n")
    GitHelpers.git(py, "add", ".")
    GitHelpers.git(py, "commit", "-qm", "unpushed core change")   # NOT pushed to origin
    rc = _run_argv(["pre", "--base", str(py), "--push"])          # post_verify refuses (returns RC)
    assert not rc and "origin/main" in (rc.error() or "")
    assert GitHelpers.git(py_remote, "tag", "--list") == ""       # nothing cut/pushed


def test_yank_push_rolls_remote_pre_back(remotes):
    """yank --push: the remote tag is renamed and the remote `pre` branch is rolled back (local==remote)."""
    py, cxx, _py_remote, _cxx_remote = remotes
    _run_pre(py, "--push")                                   # rc1
    _change_kernel_source(cxx, "feature.py")
    GitHelpers.git(cxx, "push", "-q", "origin", "main")
    _run_pre(py, "--push")                                   # kernel rc2
    rc1_commit = GitHelpers.tag_commit(cxx, "py10x-kernel-v0.0.1rc1")

    _run_yank(py, "py10x-kernel", "0.0.1rc2", "--push")

    live = GitHelpers.ls_remote_tags(cxx, "py10x-kernel-v*")
    assert "py10x-kernel-v0.0.1rc2" not in live and "py10x-kernel-v0.0.1rc2_yanked" in live
    # remote pre rolled back to the previous rc; local == remote
    assert GitHelpers.ls_remote_ref(cxx, "refs/heads/pre/py10x-kernel") == rc1_commit
    assert GitHelpers.git(cxx, "rev-parse", "pre/py10x-kernel") == rc1_commit


def test_someone_else_promoted_stale_dev_new_tags_pyproject_change(remotes, capsys):
    """When someone else promotes (new release tags, stale dev markers deleted on remote + pyproject
    epilogue commit on main), a local clone that hasn't pulled will fail require_synced on the main
    rev check (require_clean does *not* fail on tag mismatch; it only checks working tree).

    After `git pull`, main matches; the tag reconciliation in require_synced cleans stale local
    dev tags and fetches missing new release tags, allowing the promote command to succeed.

    This is the realistic "someone else promoted while you were behind" scenario.
    """
    py, _cxx, py_remote, _cxx_remote = remotes

    # Pre-create a dev marker tag that the promote will treat as stale (will be deleted during promote)
    stale_dev = "v0.0.1rc0.dev"
    GitHelpers.git(py, "tag", stale_dev, "main")
    GitHelpers.git(py, "push", "-q", "origin", f"refs/tags/{stale_dev}")

    # Local change so the promote has a footprint change and will write epilogue (pyproject update on main)
    _write(py / "src.py", "x = 1\n")
    GitHelpers.git(py, "add", ".")
    GitHelpers.git(py, "commit", "-qm", "change before promote")

    # Push the change commit so the upcoming promote's require_synced sees local main == origin/main
    GitHelpers.git(py, "push", "-q", "origin", "main")
    old_main = GitHelpers.git(py, "rev-parse", "main")

    # "Someone else" promotes: this does the epilogue commit on main (pyproject pin changes),
    # creates new release tag + new dev marker, deletes stale_dev locally+pushes delete ref.
    _run_pre(py, "--push")

    # Simulate your local not having pulled the advance:
    GitHelpers.git(py, "reset", "--hard", old_main)

    # Re-create the now-stale dev tag locally (remote no longer has it)
    GitHelpers.git(py, "tag", stale_dev, old_main)

    # First attempt: fails because local main (old) != origin/main (the epilogue commit)
    # Tag reconciliation code is not reached (main check is before it).
    # require_clean did not crash (tag mismatch alone does not make tree dirty).
    # (Note: the fetch inside this call will prune-tags the stale and bring new tags.)
    out = _run_argv(["pre", "--base", str(py), "--push"])
    assert not out
    assert "local main != origin/main" in (out.error() or "")

    # Re-create stale *after* the fetch that happened in the failing call (so reconcile on next will see it)
    GitHelpers.git(py, "tag", stale_dev, old_main)

    # Remove the new release tag locally (it was brought by the previous fetch) so the *next* reconcile fetches it
    new_release = "v0.0.1rc1"
    if new_release in GitHelpers.list_tags(py, "v*"):
        GitHelpers.git(py, "tag", "-d", new_release)

    # Now pull (catch up on the main commit with pyproject changes)
    GitHelpers.git(py, "pull", "-q", "origin", "main")

    # Second attempt: main now matches. require_synced runs tag reconciliation:
    # - deletes the stale_dev (only_local)
    # - fetches the missing new_release (only_remote)
    # Succeeds (no error from require_synced).
    out = _run_argv(["pre", "--base", str(py), "--push"])
    assert out, out.error() if not out else ""

    # Reconciliation (and/or prune-tags + tag fetch in require_synced) effects visible after pull + successful require
    assert stale_dev not in GitHelpers.list_tags(py, "v*")
    assert new_release in GitHelpers.list_tags(py, "v*")
    # (The 'cleaned stale...' print may or may not appear depending on timing with --prune-tags fetch.)
