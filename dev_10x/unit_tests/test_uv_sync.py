"""Unit tests for pure helpers in `dev_10x.uv_sync`."""
from __future__ import annotations

from pathlib import Path

from dev_10x import uv_sync as us
from dev_10x.uv_sync import _normalize_git_url, _swap_repo


class TestNormalizeGitUrl:
    def test_https_unchanged(self):
        url = 'https://github.com/org/py10x.git'
        assert _normalize_git_url(url) == url

    def test_ssh_scheme_unchanged(self):
        url = 'ssh://git@github.com/org/py10x.git'
        assert _normalize_git_url(url) == url

    def test_scp_converted(self):
        assert _normalize_git_url('git@github.com:org/py10x.git') == \
               'ssh://git@github.com/org/py10x.git'

    def test_scp_nested_path(self):
        assert _normalize_git_url('git@github.com:org/sub/repo.git') == \
               'ssh://git@github.com/org/sub/repo.git'

    def test_scp_no_dotgit(self):
        assert _normalize_git_url('git@github.com:org/repo') == \
               'ssh://git@github.com/org/repo'

    def test_scp_custom_user(self):
        assert _normalize_git_url('myuser@bitbucket.org:team/repo.git') == \
               'ssh://myuser@bitbucket.org/team/repo.git'


class TestSwapRepo:
    def test_https(self):
        assert _swap_repo('https://github.com/org/py10x.git', 'cxx10x') == \
               'https://github.com/org/cxx10x.git'

    def test_scp_preserved(self):
        # _swap_repo preserves the form; normalization is applied later in install_git
        assert _swap_repo('git@github.com:org/py10x.git', 'cxx10x') == \
               'git@github.com:org/cxx10x.git'


class TestInstalledSource:
    def test_installed_direct_url_uses_uv_run_no_sync(self, monkeypatch):
        calls = []

        def fake_check_output(args, **kwargs):
            calls.append(args)
            return ''

        monkeypatch.setattr(us.subprocess, 'check_output', fake_check_output)

        assert us._installed_direct_url('pkg') == ''
        assert calls[0][:4] == ['uv', 'run', '--no-sync', 'python']
        assert len(calls[0]) == 6
        assert "n='pkg'" in calls[0][-1]

    def test_editable_direct_url_is_local(self, monkeypatch):
        monkeypatch.setattr(
            us, '_installed_direct_url',
            lambda _name: '{"url":"file:///tmp/pkg","dir_info":{"editable":true}}')

        assert us.installed_source('pkg') == ('local', Path('/tmp/pkg'))

    def test_missing_direct_url_is_index(self, monkeypatch):
        monkeypatch.setattr(us, '_installed_direct_url', lambda _name: '')

        assert us.installed_source('pkg') == ('index', None)
