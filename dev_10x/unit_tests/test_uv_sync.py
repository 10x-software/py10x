"""Unit tests for pure helpers in `dev_10x.uv_sync`."""

from __future__ import annotations

from unittest.mock import MagicMock

from dev_10x.uv_sync import _normalize_git_url, _parse_with_downstream, _swap_repo, packages


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
