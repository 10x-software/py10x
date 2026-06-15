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


def test_repo_relative_subtree():
    repo = Path("/proj/cxx10x")
    assert GitHelpers.repo_relative_subtree(repo, repo) == "."
    assert GitHelpers.repo_relative_subtree(repo, Path("/proj/cxx10x/core_10x")) == "core_10x"


def test_diff_pathspecs():
    repo = Path("/proj/cxx10x")
    # whole-repo package (py10x-core): `.` already covers .github/workflows
    assert GitHelpers.diff_pathspecs(Path("/proj/py10x"), Path("/proj/py10x")) == (".",)
    # subdir sibling: subtree + workflow glob keyed off the subdir name
    assert GitHelpers.diff_pathspecs(repo, repo / "core_10x") == (
        "core_10x", ".github/workflows/core_10x*")
    assert GitHelpers.diff_pathspecs(repo, repo / "infra_10x") == (
        "infra_10x", ".github/workflows/infra_10x*")


def test_tree_changed_since_tag(tmp_path):
    repo = tmp_path / "repo"
    pkg = repo / "pkg"
    wf = repo / ".github" / "workflows"
    other = repo / "other"
    pkg.mkdir(parents=True)
    wf.mkdir(parents=True)
    other.mkdir()
    (pkg / "a.txt").write_text("v1\n", encoding="utf-8")
    (wf / "pkg_wheels.yml").write_text("on: [push]\n", encoding="utf-8")
    (other / "b.txt").write_text("other\n", encoding="utf-8")
    GitHelpers.git(repo, "init")
    GitHelpers.git(repo, "config", "user.email", "test@example.com")
    GitHelpers.git(repo, "config", "user.name", "Test")
    GitHelpers.git(repo, "add", ".")
    GitHelpers.git(repo, "commit", "-m", "init")
    GitHelpers.git(repo, "tag", "v0.1.0rc1")

    # Mirror diff_pathspecs for a subdir sibling: subtree + a workflow glob keyed off the subdir.
    wf_glob = ".github/workflows/pkg*"
    assert not GitHelpers.tree_changed_since_tag(repo, "v0.1.0rc1", "pkg")
    assert not GitHelpers.tree_changed_since_tag(repo, "v0.1.0rc1", "pkg", wf_glob)
    assert not GitHelpers.tree_changed_since_tag(repo, "v0.1.0rc1", ".")

    (other / "b.txt").write_text("other v2\n", encoding="utf-8")
    GitHelpers.git(repo, "add", "other/b.txt")
    GitHelpers.git(repo, "commit", "-m", "other only")

    # A change outside both the subtree and the workflow glob must not trip the diff.
    assert not GitHelpers.tree_changed_since_tag(repo, "v0.1.0rc1", "pkg", wf_glob)
    assert GitHelpers.tree_changed_since_tag(repo, "v0.1.0rc1", ".")

    # A workflow-only change (outside the source subtree) must trip the glob pathspec.
    (wf / "pkg_wheels.yml").write_text("on: [push, workflow_dispatch]\n", encoding="utf-8")
    GitHelpers.git(repo, "add", ".github/workflows/pkg_wheels.yml")
    GitHelpers.git(repo, "commit", "-m", "workflow change")
    assert not GitHelpers.tree_changed_since_tag(repo, "v0.1.0rc1", "pkg")
    assert GitHelpers.tree_changed_since_tag(repo, "v0.1.0rc1", "pkg", wf_glob)

    (pkg / "a.txt").write_text("v2\n", encoding="utf-8")
    GitHelpers.git(repo, "add", "pkg/a.txt")
    GitHelpers.git(repo, "commit", "-m", "pkg change")

    assert GitHelpers.tree_changed_since_tag(repo, "v0.1.0rc1", "pkg")


def test_latest_matching_tag_dev_pin_picks_latest_rc():
    """Form A dev pin (prereleases on) -> the latest rc tag for the target."""
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
    assert VersionHelpers.test_group_pin("0.2.3") == "py10x-core==0.2.3"


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
    """Form A must admit a sibling's dev/a/b/rc, exclude its final + next line, and auto-enable."""
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
        {'head_branch': 'v0.2.1', 'created_at': '2026-01-02T00:00:00Z', 'status': 'completed',
         'conclusion': 'success', 'html_url': 'u-new'},
        {'head_branch': 'v0.2.1', 'created_at': '2026-01-01T00:00:00Z', 'status': 'completed',
         'conclusion': 'failure', 'html_url': 'u-old'},
        {'head_branch': 'v0.3.0', 'created_at': '2026-01-03T00:00:00Z', 'status': 'in_progress',
         'conclusion': None, 'html_url': 'u-other'},
    ]

    def test_picks_latest_matching(self):
        run = GitHubHelpers.select_run_for_tag(self.RUNS, 'v0.2.1')
        assert run is not None and run['html_url'] == 'u-new'

    def test_none_when_no_match(self):
        assert GitHubHelpers.select_run_for_tag(self.RUNS, 'v9.9.9') is None


class TestRunState:
    def test_completed_reports_conclusion(self):
        assert GitHubHelpers.run_state(
            {'status': 'completed', 'conclusion': 'failure'}) == 'failure'

    def test_in_flight_reports_status(self):
        assert GitHubHelpers.run_state(
            {'status': 'in_progress', 'conclusion': None}) == 'in_progress'

    def test_none_run(self):
        assert GitHubHelpers.run_state(None) == 'no workflow run found'
