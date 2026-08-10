"""Unit tests for pure helpers in `dev_10x.uv_sync`."""

from __future__ import annotations

import shutil
from unittest.mock import MagicMock

import pytest
import setuptools_scm
from core_10x.environment_variables import EnvVars
from packaging.version import Version

from dev_10x.uv_sync import (
    PROJECT_ROOT,
    _no_build_isolation_packages,
    _normalize_git_url,
    _parse_with_downstream,
    _swap_repo,
    _workspace_member_paths,
    packages,
    source_version,
)
from dev_10x.xx_helpers import GitHelpers

requires_git = pytest.mark.skipif(shutil.which('git') is None and not EnvVars.test_strict, reason='git not available')


class TestNormalizeGitUrl:
    def test_https_unchanged(self):
        url = 'https://github.com/org/py10x.git'
        assert _normalize_git_url(url) == url

    def test_ssh_scheme_unchanged(self):
        url = 'ssh://git@github.com/org/py10x.git'
        assert _normalize_git_url(url) == url

    def test_scp_converted(self):
        assert _normalize_git_url('git@github.com:org/py10x.git') == 'ssh://git@github.com/org/py10x.git'

    def test_scp_nested_path(self):
        assert _normalize_git_url('git@github.com:org/sub/repo.git') == 'ssh://git@github.com/org/sub/repo.git'

    def test_scp_no_dotgit(self):
        assert _normalize_git_url('git@github.com:org/repo') == 'ssh://git@github.com/org/repo'

    def test_scp_custom_user(self):
        assert _normalize_git_url('myuser@bitbucket.org:team/repo.git') == 'ssh://myuser@bitbucket.org/team/repo.git'


class TestSwapRepo:
    def test_https(self):
        assert _swap_repo('https://github.com/org/py10x.git', 'cxx10x') == 'https://github.com/org/cxx10x.git'

    def test_scp_preserved(self):
        # _swap_repo preserves the form; normalization is applied later in install_git
        assert _swap_repo('git@github.com:org/py10x.git', 'cxx10x') == 'git@github.com:org/cxx10x.git'


class TestWithDownstream:
    def test_parse_flag_and_names(self):
        enabled, names, rest = _parse_with_downstream(('--all-extras', '--with-downstream', 'py10x-fin-base', '--quiet'))
        assert enabled and names == {'py10x-fin-base'} and rest == ['--all-extras', '--quiet']

    def test_parse_flag_alone_means_all(self):
        enabled, names, rest = _parse_with_downstream(('--with-downstream',))
        assert enabled and names is None and rest == []

    def test_default_omits_downstream(self):
        all_pkgs = {
            'py10x-core': {'downstream': False},
            'py10x-kernel': {'downstream': False},
            'py10x-fin-base': {'downstream': True},
        }
        default = {n: p for n, p in all_pkgs.items() if not p.get('downstream')}
        assert set(default) == {'py10x-core', 'py10x-kernel'}

    def test_packages_marks_downstream_cxx_false(self, monkeypatch):
        monkeypatch.setattr('dev_10x.uv_sync._git_remote', lambda: 'https://github.com/org/py10x.git')
        monkeypatch.setattr(
            'dev_10x.uv_sync._dev10x_cfg',
            lambda _t: {
                'siblings': {'py10x-kernel': {'path': '../cxx10x/core_10x'}},
                'downstream': {'py10x-fin-base': {'path': 'xx_fin'}},
            },
        )
        pkgs = packages(MagicMock())
        assert pkgs['py10x-fin-base']['downstream'] is True
        assert pkgs['py10x-fin-base']['cxx'] is False
        assert pkgs['py10x-fin-base']['subdir'] == 'xx_fin'
        assert pkgs['py10x-kernel']['downstream'] is False
        assert pkgs['py10x-kernel']['cxx'] is True

    def test_no_build_isolation_packages_reads_tool_uv(self, tmp_path):
        (tmp_path / 'pyproject.toml').write_text(
            '[project]\nname = "py10x-fin-base"\n\n[tool.uv]\nno-build-isolation-package = ["py10x-fin-base-cxx"]\n',
            encoding='utf-8',
        )
        assert _no_build_isolation_packages(tmp_path) == ['py10x-fin-base-cxx']

    def test_no_build_isolation_packages_empty_without_section(self, tmp_path):
        (tmp_path / 'pyproject.toml').write_text('[project]\nname = "x"\n', encoding='utf-8')
        assert _no_build_isolation_packages(tmp_path) == []

    def test_live_fin_base_declares_cxx_no_isolation(self):
        fin = PROJECT_ROOT / 'xx_fin'
        if not (fin / 'pyproject.toml').is_file():
            return
        assert 'py10x-fin-base-cxx' in _no_build_isolation_packages(fin)
        members = _workspace_member_paths(fin)
        assert members.get('py10x-fin-base-cxx') == (fin / 'cxxfin').resolve()

    def test_workspace_member_paths(self, tmp_path):
        (tmp_path / 'pyproject.toml').write_text(
            '[project]\nname = "parent"\n\n[tool.uv.workspace]\nmembers = ["child"]\n',
            encoding='utf-8',
        )
        child = tmp_path / 'child'
        child.mkdir()
        (child / 'pyproject.toml').write_text('[project]\nname = "child-dist"\n', encoding='utf-8')
        assert _workspace_member_paths(tmp_path) == {'child-dist': child.resolve()}

    @requires_git
    def test_source_version_root_uses_hatch_v_match_not_fin_base_tags(self, tmp_path):
        """Hatch ``--match 'v*'`` must win over a nearer ``py10x-fin-base-v*`` tag at repo root."""
        repo = tmp_path / 'mono'
        fin = repo / 'xx_fin'
        fin.mkdir(parents=True)
        (repo / 'pyproject.toml').write_text(
            '[project]\nname = "py10x-core"\n'
            '[tool.hatch.version]\nsource = "vcs"\n'
            'raw-options = { git_describe_command = '
            '"git describe --dirty --tags --long --match \'v*\'" }\n',
            encoding='utf-8',
        )
        (fin / 'pyproject.toml').write_text(
            '[project]\nname = "py10x-fin-base"\n'
            '[tool.hatch.version]\nsource = "vcs"\n'
            '[tool.hatch.version.raw-options]\n'
            'root = ".."\n'
            'git_describe_command = "git describe --dirty --tags --long --match \'py10x-fin-base-v*\'"\n',
            encoding='utf-8',
        )
        GitHelpers.git(repo, 'init', '-q', '-b', 'main')
        GitHelpers.git(repo, 'config', 'user.email', 'test@example.com')
        GitHelpers.git(repo, 'config', 'user.name', 'Test')
        GitHelpers.git(repo, 'add', '.')
        GitHelpers.git(repo, 'commit', '-qm', 'init')
        # Older core release tag, then a newer fin-base tag on a later commit (nearest-any-tag trap).
        GitHelpers.git(repo, 'tag', 'v0.2.0')
        (fin / 'marker.txt').write_text('x\n', encoding='utf-8')
        GitHelpers.git(repo, 'add', '.')
        GitHelpers.git(repo, 'commit', '-qm', 'fin-base bump')
        GitHelpers.git(repo, 'tag', 'py10x-fin-base-v0.1.0rc1')
        (repo / 'core_touch.txt').write_text('y\n', encoding='utf-8')
        GitHelpers.git(repo, 'add', '.')
        GitHelpers.git(repo, 'commit', '-qm', 'core touch')

        # Control: unfiltered setuptools_scm at root follows the nearer fin-base tag.
        assert Version(setuptools_scm.get_version(root=str(repo))).minor == 1

        core_v = Version(source_version(repo))
        fin_v = Version(source_version(fin))
        assert core_v.minor == 2
        assert fin_v.minor == 1
        assert core_v != fin_v
