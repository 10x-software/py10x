"""Unit tests for `dev_10x.xx_utils` pure helpers and PEP 440 assumption guards.

If a future `packaging`/uv release changes how the emitted specifiers behave, the assumption
guards fail loudly so an incompatible release is never published.
"""
from __future__ import annotations

import textwrap
import tomlkit
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from pathlib import Path

import pytest

from dev_10x.xx_helpers import (
    GitHelpers,
    GitHubHelpers,
    InstalledSourceHelpers,
    PyProjectHelpers,
    PyPIHelpers,
    VersionHelpers,
)

KERNEL = "py10x-kernel-v"

# A representative tag set for py10x-kernel: older finals, the latest final, two rc's for the next
# version, a yanked final, and a non-version tag - the last two must be ignored.
TAGS = [
    f"{KERNEL}0.1.16",
    f"{KERNEL}0.2.0",
    f"{KERNEL}0.2.1rc1",
    f"{KERNEL}0.2.1rc2",
    f"{KERNEL}0.2.1_yanked",
    "not-a-tag",
]


def parsed():
    return VersionHelpers.parse_pkg_tags(TAGS, KERNEL)


# --------------------------------------------------------------------------- tag parsing/selection
def test_parse_drops_unmatched_and_unparseable():
    got = {t for t, _ in parsed()}
    assert got == {f"{KERNEL}0.1.16", f"{KERNEL}0.2.0", f"{KERNEL}0.2.1rc1", f"{KERNEL}0.2.1rc2"}
    assert f"{KERNEL}0.2.1_yanked" not in got


def test_latest_final_excludes_pre_and_yanked():
    assert VersionHelpers.latest_final(parsed()) == Version("0.2.0")


def test_target_and_next_micro():
    assert VersionHelpers.target_version(parsed()) == "0.2.1"
    assert VersionHelpers.next_micro("0.2.0") == "0.2.1"
    assert VersionHelpers.next_micro("0.2.9") == "0.2.10"
    assert VersionHelpers.next_micro("1.0") == "1.0.1"


def test_next_rc_numbering():
    assert VersionHelpers.next_rc(parsed(), "0.2.1") == 3     # rc1, rc2 -> 3
    assert VersionHelpers.next_rc(parsed(), "0.3.0") == 1     # none yet -> 1


def test_main_dev_markers_excluded_from_release_selection():
    """`*.dev` tags on `main` are for setuptools-scm only — not releases or rc numbering."""
    tags = [f"{KERNEL}0.2.1rc17", f"{KERNEL}0.2.1rc18.dev", f"{KERNEL}0.2.2rc0.dev", f"{KERNEL}0.2.1"]
    parsed = VersionHelpers.parse_pkg_tags(tags, KERNEL)
    assert parsed == [(f"{KERNEL}0.2.1rc17", Version("0.2.1rc17")), (f"{KERNEL}0.2.1", Version("0.2.1"))]
    assert VersionHelpers.latest_tag(parsed) == (f"{KERNEL}0.2.1", Version("0.2.1"))
    assert VersionHelpers.next_rc(parsed, "0.2.1") == 18
    assert VersionHelpers.main_dev_marker_tag(f"{KERNEL}0.2.1rc17", KERNEL) == f"{KERNEL}0.2.1rc18.dev"
    assert VersionHelpers.main_post_final_dev_marker_tag(f"{KERNEL}0.2.1", KERNEL) == f"{KERNEL}0.2.2rc0.dev"
    assert Version("0.2.2rc0.dev0") > Version("0.2.1")
    assert Version("0.2.2rc0.dev0") < Version("0.2.2rc1")


def test_latest_rc_tag():
    assert VersionHelpers.latest_rc_tag(parsed(), "0.2.1") == f"{KERNEL}0.2.1rc2"   # rc2 > rc1
    assert VersionHelpers.latest_rc_tag(parsed(), "0.3.0") is None                  # none yet


def test_latest_tag_picks_highest_rc_or_final():
    tag, ver = VersionHelpers.latest_tag(parsed())
    assert tag == f"{KERNEL}0.2.1rc2" and ver == Version("0.2.1rc2")
    p = VersionHelpers.parse_pkg_tags([f"{KERNEL}0.2.1"], KERNEL)
    assert VersionHelpers.latest_tag(p) == (f"{KERNEL}0.2.1", Version("0.2.1"))
    assert VersionHelpers.latest_tag([]) is None


def test_pending_promotions_only_since_latest_pypi_release():
    """Tags strictly after the latest PyPI release are pending; older unpublished ones are dropped."""
    # parsed() has finals 0.1.16, 0.2.0 and rc's 0.2.1rc1/rc2. With 0.2.0 published, only the
    # 0.2.1 rc's remain pending; the old 0.1.16 final stays below the floor and is ignored.
    pending = VersionHelpers.pending_promotions(parsed(), {Version("0.2.0")})
    assert [t for t, _ in pending] == [f"{KERNEL}0.2.1rc1", f"{KERNEL}0.2.1rc2"]


def test_pending_promotions_empty_when_frontier_published():
    assert VersionHelpers.pending_promotions(parsed(), {Version("0.2.1rc2")}) == []


def test_pending_promotions_unpublished_project_reports_latest_only():
    """No PyPI releases yet -> just the single latest tag (the in-flight first release)."""
    pending = VersionHelpers.pending_promotions(parsed(), set())
    assert [t for t, _ in pending] == [f"{KERNEL}0.2.1rc2"]
    assert VersionHelpers.pending_promotions([], set()) == []


def test_publish_trigger_tag_naming():
    assert VersionHelpers.publish_trigger_tag(f"{KERNEL}0.2.1rc5", "pre") == f"pre/{KERNEL}0.2.1rc5"
    assert VersionHelpers.publish_trigger_tag(f"{KERNEL}0.2.1", "prod") == f"prod/{KERNEL}0.2.1"
    assert VersionHelpers.existing_publish_trigger_tags(
        [f"pre/{KERNEL}0.2.1rc4", f"pre/{KERNEL}0.2.1rc5", f"prod/{KERNEL}0.2.1"],
        KERNEL) == [f"pre/{KERNEL}0.2.1rc4", f"pre/{KERNEL}0.2.1rc5", f"prod/{KERNEL}0.2.1"]
    # promote lists only `{flavor}/*` so pre never deletes a prod trigger (and vice versa)
    pre_only = [t for t in [f"pre/{KERNEL}0.2.1rc4", f"prod/{KERNEL}0.2.1"] if t.startswith("pre/")]
    assert VersionHelpers.existing_publish_trigger_tags(pre_only, KERNEL) == [f"pre/{KERNEL}0.2.1rc4"]
    assert VersionHelpers.publish_trigger_flavor(Version("0.2.1rc1")) == "pre"
    assert VersionHelpers.publish_trigger_flavor(Version("0.2.1")) == "prod"


def test_publish_release_tag_selects_latest_rc_or_final():
    parsed = VersionHelpers.parse_pkg_tags(
        [f"{KERNEL}0.2.1rc4", f"{KERNEL}0.2.1rc5", f"{KERNEL}0.2.1"], KERNEL)
    assert VersionHelpers.publish_release_tag(parsed, "pre") == f"{KERNEL}0.2.1rc5"
    assert VersionHelpers.publish_release_tag(parsed, "prod") == f"{KERNEL}0.2.1"


def test_repo_relative_subtree():
    repo = Path("/proj/cxx10x")
    assert GitHelpers.repo_relative_subtree(repo, repo) == "."
    assert GitHelpers.repo_relative_subtree(repo, Path("/proj/cxx10x/core_10x")) == "core_10x"


def test_diff_pathspecs():
    # a package alone in its repo (no siblings) -> the whole repo
    assert GitHelpers.diff_pathspecs() == (".",)
    # a sibling: the whole repo with the *other* package subtrees excluded (shared files still count)
    assert GitHelpers.diff_pathspecs("infra_10x") == (".", ":(exclude)infra_10x")
    assert GitHelpers.diff_pathspecs("core_10x", "infra_10x") == (
        ".", ":(exclude)core_10x", ":(exclude)infra_10x")


def test_tree_changed_since_tag(tmp_path):
    repo = tmp_path / "repo"
    for d in ("pkg", "sib", ".github/actions"):
        (repo / d).mkdir(parents=True)
    (repo / "pkg" / "a.txt").write_text("v1\n", encoding="utf-8")          # this package's subtree
    (repo / "sib" / "b.txt").write_text("v1\n", encoding="utf-8")          # a sibling package's subtree
    (repo / ".github" / "actions" / "build.yml").write_text("v1\n", encoding="utf-8")  # shared CI
    (repo / "CMakeLists.txt").write_text("v1\n", encoding="utf-8")         # shared root build config
    GitHelpers.git(repo, "init")
    GitHelpers.git(repo, "config", "user.email", "test@example.com")
    GitHelpers.git(repo, "config", "user.name", "Test")
    GitHelpers.git(repo, "add", ".")
    GitHelpers.git(repo, "commit", "-m", "init")
    GitHelpers.git(repo, "tag", "base")

    fp = GitHelpers.diff_pathspecs("sib")          # footprint of `pkg`: whole repo minus sibling `sib`
    assert not GitHelpers.tree_changed_since_tag(repo, "base", *fp)        # no change yet

    def footprint_trips(path: str) -> bool:
        (repo / path).write_text("v2\n", encoding="utf-8")
        GitHelpers.git(repo, "add", ".")
        GitHelpers.git(repo, "commit", "-qm", f"touch {path}")
        tripped = GitHelpers.tree_changed_since_tag(repo, "base", *fp)
        GitHelpers.git(repo, "tag", "-f", "base")  # re-baseline so the next case is isolated
        return tripped

    assert footprint_trips("sib/b.txt") is False                  # a sibling's subtree -> excluded
    assert footprint_trips("pkg/a.txt") is True                   # own subtree -> trips
    assert footprint_trips(".github/actions/build.yml") is True   # shared CI -> trips
    assert footprint_trips("CMakeLists.txt") is True              # shared root build config -> trips


def test_latest_matching_tag_dev_pin_picks_latest_rc():
    """Prerelease-admitting dev pin (prereleases on) -> the latest rc tag for the target."""
    spec = VersionHelpers.dev_pin("0.2.0", "0.2.1")
    assert VersionHelpers.latest_matching_tag(parsed(), spec) == f"{KERNEL}0.2.1rc2"


def test_latest_matching_tag_final_pin_picks_final():
    """Final-only pin (prereleases off) -> the final tag, never an rc."""
    p = VersionHelpers.parse_pkg_tags(
        [f"{KERNEL}0.2.0", f"{KERNEL}0.2.1rc1", f"{KERNEL}0.2.1"], KERNEL)
    assert VersionHelpers.latest_matching_tag(p, VersionHelpers.final_pin("0.2.1")) == f"{KERNEL}0.2.1"


def test_latest_matching_tag_none_when_no_match():
    assert VersionHelpers.latest_matching_tag(parsed(), ">=9.9.9") is None


# ------------------------------------------------------------------------------------ pin builders
def test_pin_strings():
    assert VersionHelpers.dev_pin("0.2.0", "0.2.1") == ">=0.2.0,<=0.2.1,!=0.2.1,>=0.0.0.dev0"
    assert VersionHelpers.final_pin("0.2.1") == ">=0.2.1,<0.2.2"
    assert VersionHelpers.exact_pin("0.2.1rc2") == "==0.2.1rc2"   # forward, rc
    assert VersionHelpers.exact_pin("0.2.1") == "==0.2.1"         # forward, final
    assert VersionHelpers.test_group_pin("0.2.3") == "py10x-core>=0.2.3"      # reverse floor, final
    assert VersionHelpers.test_group_pin("0.2.3rc1") == "py10x-core>=0.2.3rc1"  # reverse floor, rc


def test_release_branch_names():
    assert GitHelpers.release_branch("pre", "py10x-core", is_core=True) == "pre"
    assert GitHelpers.release_branch("prod", "py10x-core", is_core=True) == "prod"
    assert GitHelpers.release_branch("pre", "py10x-kernel", is_core=False) == "pre/py10x-kernel"
    assert GitHelpers.release_branch("prod", "py10x-infra", is_core=False) == "prod/py10x-infra"


def test_forward_pin_edits_targets_only_named_and_preserves_format():
    deps = [
        "py10x-kernel (>=0.2.0,<=0.2.1,!=0.2.1,>=0.0.0.dev0)",
        "py10x-infra (>=0.2.0,<=0.2.1,!=0.2.1,>=0.0.0.dev0)",
        "numpy>=2.2.2,<2.5.0",
    ]
    out = PyProjectHelpers.forward_pin_edits(deps, {"py10x-kernel": ">=0.2.1,<0.2.2"})
    assert out == [
        "py10x-kernel (>=0.2.1,<0.2.2)",
        "py10x-infra (>=0.2.0,<=0.2.1,!=0.2.1,>=0.0.0.dev0)",
        "numpy>=2.2.2,<2.5.0",
    ]


# --------------------------------------------------------------------------- pyproject rewrites I/O
def test_write_forward_pins_preserves_multiline_and_comments(tmp_path):
    """Pin edits touch only the changed dependency lines; layout and trailing comments stay put."""
    p = tmp_path / "pyproject.toml"
    p.write_text(textwrap.dedent("""
        [project]
        name = "py10x-core"
        dependencies = [
            "py10x-kernel (>=0.2.0,<=0.2.1,!=0.2.1,>=0.0.0.dev0)", # sibling kernel
            "py10x-infra (>=0.2.0,<=0.2.1,!=0.2.1,>=0.0.0.dev0)",  # sibling infra
            "numpy>=2.2.2,<2.5.0",
        ]
    """), encoding="utf-8")
    before = p.read_text()
    PyProjectHelpers.write_forward_pins(p, {"py10x-kernel": "==0.2.1rc17"})
    after = p.read_text()
    assert after != before
    assert 'py10x-kernel (==0.2.1rc17)", # sibling kernel' in after
    assert 'py10x-infra (>=0.2.0,<=0.2.1,!=0.2.1,>=0.0.0.dev0)",  # sibling infra' in after
    assert "numpy>=2.2.2,<2.5.0" in after
    assert "dependencies = [\n" in after
    assert after.count("\n") >= before.count("\n") - 1  # no collapse to one line


def test_write_forward_pins_roundtrip(tmp_path):
    p = tmp_path / "pyproject.toml"
    p.write_text(textwrap.dedent("""
        [project]
        name = "py10x-core"
        dependencies = [
            "py10x-kernel (>=0.2.0,<=0.2.1,!=0.2.1,>=0.0.0.dev0)",
            "py10x-infra (>=0.2.0,<=0.2.1,!=0.2.1,>=0.0.0.dev0)",
            "numpy>=2.2.2,<2.5.0",
        ]
    """), encoding="utf-8")
    changes = PyProjectHelpers.write_forward_pins(p, {"py10x-kernel": ">=0.2.1,<0.2.2",
                                                      "py10x-infra": ">=0.2.1,<0.2.2"})
    assert set(changes) == {"py10x-kernel", "py10x-infra"}
    body = p.read_text()
    assert 'py10x-kernel (>=0.2.1,<0.2.2)' in body
    assert 'py10x-infra (>=0.2.1,<0.2.2)' in body
    assert 'numpy>=2.2.2,<2.5.0' in body


def test_dependency_spec_reads_pinned_specifier(tmp_path):
    p = tmp_path / "pyproject.toml"
    p.write_text(textwrap.dedent("""
        [project]
        name = "py10x-core"
        dependencies = [
            "py10x-kernel (>=0.2.0,<=0.2.1,!=0.2.1,>=0.0.0.dev0)",
            "numpy>=2.2.2,<2.5.0",
        ]
    """), encoding="utf-8")
    # Requirement canonicalises specifier order, so compare as a set, not a string.
    got = PyProjectHelpers.dependency_spec(p, "py10x-kernel")
    assert SpecifierSet(got) == SpecifierSet(">=0.2.0,<=0.2.1,!=0.2.1,>=0.0.0.dev0")
    with pytest.raises(KeyError):
        PyProjectHelpers.dependency_spec(p, "py10x-infra")


def test_write_forward_pins_idempotent(tmp_path):
    """Re-applying the same pins is a byte-identical no-op (reports no changes).

    Assumption guard for the canonical/deterministic pin rewrite the design depends on: a clean
    setuptools-scm tree needs the rewrite to be stable, and Stage 2's reverse-derivation pin-only
    check relies on the rewrite not introducing cosmetic churn.
    """
    p = tmp_path / "pyproject.toml"
    p.write_text(textwrap.dedent("""
        [project]
        name = "py10x-core"
        dependencies = [
            "py10x-kernel (>=0.2.0,<=0.2.1,!=0.2.1,>=0.0.0.dev0)",
            "numpy>=2.2.2,<2.5.0",
        ]
    """), encoding="utf-8")
    pins = {"py10x-kernel": ">=0.2.1,<0.2.2"}
    assert set(PyProjectHelpers.write_forward_pins(p, pins)) == {"py10x-kernel"}
    once = p.read_text()
    assert PyProjectHelpers.write_forward_pins(p, pins) == {}   # second pass: nothing to change
    assert p.read_text() == once                                # and the bytes are unchanged


def test_write_test_group_idempotent(tmp_path):
    p = tmp_path / "pyproject.toml"
    p.write_text('[project]\nname = "py10x-kernel"\ndependencies = ["uuid6>=2025.0.1"]\n',
                 encoding="utf-8")
    PyProjectHelpers.write_test_group(p, "py10x-core>=0.2.3")
    once = p.read_text()
    PyProjectHelpers.write_test_group(p, "py10x-core>=0.2.3")
    assert p.read_text() == once


def test_write_test_group_creates_and_refreshes(tmp_path):
    p = tmp_path / "pyproject.toml"
    p.write_text('[project]\nname = "py10x-kernel"\ndependencies = ["uuid6>=2025.0.1"]\n',
                 encoding="utf-8")
    PyProjectHelpers.write_test_group(p, "py10x-core==0.2.3")
    doc = tomlkit.parse(p.read_text())
    assert list(doc["dependency-groups"]["test"]) == ["py10x-core==0.2.3"]
    PyProjectHelpers.write_test_group(p, "py10x-core==0.2.4")
    doc = tomlkit.parse(p.read_text())
    assert list(doc["dependency-groups"]["test"]) == ["py10x-core==0.2.4"]


# ------------------------------------------------------------- PEP 440 / resolver assumption guards
ADMIT_MATRIX = ["0.2.0", "0.2.1.dev1", "0.2.1a1", "0.2.1b1", "0.2.1rc1", "0.2.1rc2",
                "0.2.1", "0.2.1.post1", "0.2.2.dev0", "0.2.2"]


def test_dev_pin_admits_pre_excludes_final_and_autoenables():
    """The prerelease-admitting dev pin must admit a sibling's dev/a/b/rc, exclude its final + next line, and auto-enable."""
    ss = SpecifierSet(VersionHelpers.dev_pin("0.2.0", "0.2.1"))
    assert ss.prereleases is True
    eligible = set(ss.filter(ADMIT_MATRIX))
    assert eligible == {"0.2.0", "0.2.1.dev1", "0.2.1a1", "0.2.1b1", "0.2.1rc1", "0.2.1rc2"}
    for excluded in ("0.2.1", "0.2.1.post1", "0.2.2.dev0", "0.2.2"):
        assert excluded not in eligible


def test_final_pin_admits_only_final_line_no_prereleases():
    ss = SpecifierSet(VersionHelpers.final_pin("0.2.1"))
    assert not ss.prereleases
    eligible = set(ss.filter(ADMIT_MATRIX))
    assert eligible == {"0.2.1", "0.2.1.post1"}
    for excluded in ("0.2.1rc2", "0.2.0", "0.2.2"):
        assert excluded not in eligible


def test_empty_set_trap_is_guarded():
    """`>=Trc1,<T` is empty because `<T` excludes pre-releases of T - a trap we must never emit."""
    assert list(SpecifierSet(">=0.2.1rc1,<0.2.1").filter(ADMIT_MATRIX)) == []


def test_version_ordering_not_sort_v():
    """`max(Version)` orders dev < rc < final; `sort -V`/`git -v:refname` get this wrong."""
    vs = [Version(v) for v in ["0.2.1", "0.2.1rc1", "0.2.1.dev5"]]
    assert max(vs) == Version("0.2.1")
    assert sorted(vs) == [Version("0.2.1.dev5"), Version("0.2.1rc1"), Version("0.2.1")]


@pytest.mark.parametrize("yanked_floor,expected_pin", [
    ("0.2.0", ">=0.2.0,<=0.2.1,!=0.2.1,>=0.0.0.dev0"),
])
def test_yank_rollback_floor(yanked_floor, expected_pin):
    """After a prod yank the remaining latest final becomes the floor and target advances by one."""
    assert VersionHelpers.dev_pin(yanked_floor, VersionHelpers.next_micro(yanked_floor)) == expected_pin


# ---------------------------------------- rc-branch-promotion coordination pin forms (design note)
#
# Assumption guards for the cross-repo coordination pins proposed in
# `dev_10x/docs/rc-branch-promotion.md` (Pin matrix):
#   - forward (core -> siblings) on `pre`/`prod`: exact `==` coordinated version.
#   - reverse (sibling `test` group -> core) on `pre`/`prod`: `>=` coordinated version.
# These lock the PEP 440 / resolver behavior the design *depends on* before any builder is wired up.
# Live multi-package resolution (backtracking) is an execution concern covered by the e2e tier; here
# we guard only the specifier semantics that make that argument hold.
#
# A sibling's candidate tags around target 1.4.0, plus its `.post` and a newer line (1.4.1, 1.5.0rc1)
# that the forward `==` must exclude and the reverse `>=` must (or must not) admit.
COORD_MATRIX = ["1.3.9", "1.4.0rc1", "1.4.0rc2", "1.4.0", "1.4.0.post1",
                "1.4.1rc1", "1.4.1", "1.5.0rc1"]


def test_forward_exact_rc_pin_selects_only_that_rc_and_autoenables():
    """Published rc wheel pins exactly one sibling rc; `==<pre>` auto-enables prereleases for free.

    The external coordination guarantee: `pip install core==X.Yrc2` must drag in exactly the
    coordinated sibling rc, and an exact pin onto a pre-release flips prerelease admission on its
    own (no `--prerelease=allow`), the analogue of `dev_pin`'s PRERELEASE_ENABLE token.
    """
    ss = SpecifierSet("==1.4.0rc2")
    assert ss.prereleases is True
    assert set(ss.filter(COORD_MATRIX)) == {"1.4.0rc2"}


def test_forward_exact_final_pin_selects_only_that_final():
    """Released wheel pins exactly the coordinated final - not its own rc, not its `.post`, not the next line."""
    ss = SpecifierSet("==1.4.0")
    assert not ss.prereleases
    assert set(ss.filter(COORD_MATRIX)) == {"1.4.0"}
    for excluded in ("1.4.0rc2", "1.4.0.post1", "1.4.1", "1.5.0rc1"):
        assert excluded not in set(ss.filter(COORD_MATRIX))


def test_reverse_floor_rc_admits_prereleases():
    """Reverse `>=Tc_rcN` admits core prereleases - the rc sibling tests the prerelease core line.

    The prerelease token "falls out for free": naming a pre-release in the floor flips admission on.
    There is deliberately no upper cap, so a newer line's prereleases are admitted too - the design's
    acknowledged tradeoff, self-corrected by the forward `==` (see next test).
    """
    ss = SpecifierSet(">=1.4.0rc2")
    assert ss.prereleases is True
    assert set(ss.filter(COORD_MATRIX)) == {
        "1.4.0rc2", "1.4.0", "1.4.0.post1", "1.4.1rc1", "1.4.1", "1.5.0rc1"}
    assert "1.4.0rc1" not in set(ss.filter(COORD_MATRIX))  # strictly below the floor


def test_reverse_floor_final_excludes_prereleases():
    """Reverse `>=Tc` (final floor, no prerelease token) admits only finals - tests the released line."""
    ss = SpecifierSet(">=1.4.0")
    assert not ss.prereleases
    assert set(ss.filter(COORD_MATRIX)) == {"1.4.0", "1.4.0.post1", "1.4.1"}
    for excluded in ("1.4.0rc2", "1.4.1rc1", "1.5.0rc1"):
        assert excluded not in set(ss.filter(COORD_MATRIX))


def test_reverse_floor_self_corrects_via_forward_exact_pin():
    """The uncapped reverse `>=` is pinned down by the forward `==` consistency check.

    `>=1.4.0` alone admits a too-new core (1.4.1), but the sibling under test also carries the
    forward exact pin (core `kernel==1.4.0`); only the coordinated version satisfies both, so the
    resolver is driven back to it. Here we guard the set-intersection that makes that hold; the live
    backtracking behavior is exercised in the e2e tier.
    """
    floor = set(SpecifierSet(">=1.4.0").filter(COORD_MATRIX))
    assert "1.4.1" in floor  # floor alone is insufficient - it admits a newer final
    coordinated = floor & set(SpecifierSet("==1.4.0").filter(COORD_MATRIX))
    assert coordinated == {"1.4.0"}


# --------------------------------------------------------------------------- installed-source helpers
class TestParseUvPipShow:
    def test_editable(self):
        out = """\
Name: py10x-core
Version: 1.0.0
Location: /proj/.venv/lib/python3.11/site-packages
Editable project location: /proj/py10x
Requires: numpy
Required-by:
"""
        info = InstalledSourceHelpers.parse_uv_pip_show(out)
        assert info['Name'] == 'py10x-core'
        assert info['Editable project location'] == '/proj/py10x'


class TestClassifyInstall:
    def test_editable(self):
        assert InstalledSourceHelpers.classify_install(Path('/proj/py10x'), '') == (
            'local', Path('/proj/py10x'))

    def test_index(self):
        assert InstalledSourceHelpers.classify_install(None, '') == ('index', None)

    def test_git_or_direct_url(self):
        raw = '{"url":"https://github.com/org/repo.git","vcs_info":{"vcs":"git"}}'
        assert InstalledSourceHelpers.classify_install(None, raw) == ('other', None)


class TestDistInfoDirectUrl:
    def test_reads_direct_url_json(self, tmp_path):
        site = tmp_path / 'site-packages'
        dist = site / 'py10x_kernel-1.0.dist-info'
        dist.mkdir(parents=True)
        (dist / 'direct_url.json').write_text(
            '{"url":"https://github.com/org/cxx10x.git","vcs_info":{"vcs":"git"}}')
        show = {'Name': 'py10x-kernel', 'Version': '1.0', 'Location': str(site)}
        assert InstalledSourceHelpers.dist_info_direct_url(show) != ''

    def test_missing_direct_url_is_index(self, tmp_path):
        site = tmp_path / 'site-packages'
        dist = site / 'numpy-2.4.6.dist-info'
        dist.mkdir(parents=True)
        show = {'Name': 'numpy', 'Version': '2.4.6', 'Location': str(site)}
        assert InstalledSourceHelpers.dist_info_direct_url(show) == ''


class TestInstalledSourceIntegration:
    def test_against_project_venv(self):
        kind, path = InstalledSourceHelpers(Path('.')).installed_source('py10x-core')
        assert kind in ('local', 'index', 'other')
        if kind == 'local':
            assert path is not None and path.is_dir()


# ------------------------------------------------------------------ PyPI / GitHub status helpers
class TestPyPIHelpers:
    def test_parse_released_versions_drops_unparseable(self):
        body = (
            '{"releases": {"0.2.0": [], "0.2.1rc1": [], "0.2.1": [], "garbage": []}}'
        )
        got = PyPIHelpers.parse_released_versions(body)
        assert got == {Version('0.2.0'), Version('0.2.1rc1'), Version('0.2.1')}

    def test_parse_released_versions_empty(self):
        assert PyPIHelpers.parse_released_versions('{}') == set()


class TestParseRemoteSlug:
    @pytest.mark.parametrize('url,slug', [
        ('git@github.com:10x-software/py10x.git', '10x-software/py10x'),
        ('git@github.com:10x-software/py10x', '10x-software/py10x'),
        ('https://github.com/10x-software/py10x.git', '10x-software/py10x'),
        ('https://github.com/10x-software/py10x', '10x-software/py10x'),
        ('ssh://git@github.com/10x-software/cxx10x.git', '10x-software/cxx10x'),
        ('  https://github.com/10x-software/py10x/  \n', '10x-software/py10x'),
    ])
    def test_forms(self, url, slug):
        assert GitHubHelpers.parse_remote_slug(url) == slug


class TestSelectRunForTag:
    RUNS = [
        {'head_branch': 'pre/v0.2.1', 'created_at': '2026-01-02T00:00:00Z', 'status': 'completed',
         'conclusion': 'success', 'html_url': 'u-new'},
        {'head_branch': 'pre/v0.2.1', 'created_at': '2026-01-01T00:00:00Z', 'status': 'completed',
         'conclusion': 'failure', 'html_url': 'u-old'},
        {'head_branch': 'prod/v0.3.0', 'created_at': '2026-01-03T00:00:00Z', 'status': 'in_progress',
         'conclusion': None, 'html_url': 'u-other'},
    ]

    def test_picks_latest_matching(self):
        runs = [
            {'head_branch': 'pre/v0.2.1', 'created_at': '2026-01-02T00:00:00Z', 'status': 'completed',
             'conclusion': 'success', 'html_url': 'u-new'},
            {'head_branch': 'pre/v0.2.1', 'created_at': '2026-01-01T00:00:00Z', 'status': 'completed',
             'conclusion': 'failure', 'html_url': 'u-old'},
            {'head_branch': 'prod/v0.3.0', 'created_at': '2026-01-03T00:00:00Z', 'status': 'in_progress',
             'conclusion': None, 'html_url': 'u-other'},
        ]
        run = GitHubHelpers.select_run_for_tag(runs, 'pre/v0.2.1')
        assert run is not None and run['html_url'] == 'u-new'

    def test_none_when_no_match(self):
        assert GitHubHelpers.select_run_for_tag(self.RUNS, 'pre/v9.9.9') is None


class TestRunState:
    def test_completed_reports_conclusion(self):
        assert GitHubHelpers.run_state(
            {'status': 'completed', 'conclusion': 'failure'}) == 'failure'

    def test_in_flight_reports_status(self):
        assert GitHubHelpers.run_state(
            {'status': 'in_progress', 'conclusion': None}) == 'in_progress'

    def test_none_run(self):
        assert GitHubHelpers.run_state(None) == 'no workflow run found'


class TestPublishWorkflowState:
    RUNS = TestSelectRunForTag.RUNS

    def test_local_only_release(self):
        state, url = GitHubHelpers.publish_workflow_state(
            self.RUNS, 'pre/v0.2.1', release_on_origin=False, trigger_on_origin=False)
        assert state == 'not pushed to origin'
        assert url == ''

    def test_release_on_origin_but_trigger_local(self):
        state, url = GitHubHelpers.publish_workflow_state(
            self.RUNS, 'pre/v0.2.1', release_on_origin=True, trigger_on_origin=False)
        assert state == 'publish trigger not on origin (re-run with --push)'
        assert url == ''

    def test_both_on_origin_reports_workflow(self):
        state, url = GitHubHelpers.publish_workflow_state(
            self.RUNS, 'pre/v0.2.1', release_on_origin=True, trigger_on_origin=True)
        assert state == 'success'
        assert url == 'u-new'
