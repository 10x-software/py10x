"""Unit tests for pure helpers in `dev_10x.uv_sync`."""
from __future__ import annotations

import subprocess
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
    def test_target_python_requires_venv(self, monkeypatch, tmp_path):
        monkeypatch.setattr(us, '_venv_python', lambda: tmp_path / 'missing-python')

        try:
            us._target_python()
        except RuntimeError as e:
            assert 'target venv not found' in str(e)
        else:
            raise AssertionError('expected missing target venv to fail')

    def test_ensure_runtime_deps_installs_into_venv_python(self, monkeypatch, tmp_path):
        calls = []
        venv_python = tmp_path / '.venv' / 'bin' / 'python'
        venv_python.parent.mkdir(parents=True)
        venv_python.write_text('', encoding='utf-8')
        (tmp_path / '.venv' / 'pyvenv.cfg').write_text('', encoding='utf-8')

        def fake_run(args, **kwargs):
            calls.append(args)
            if args == [str(venv_python), '-c', 'import setuptools_scm']:
                raise subprocess.CalledProcessError(1, args)
            return subprocess.CompletedProcess(args, 0)

        monkeypatch.setattr(us, '_venv_python', lambda project_root=us.PROJECT_ROOT: venv_python)
        monkeypatch.setattr(us.subprocess, 'run', fake_run)

        us.ensure_env_and_runtime_deps(tmp_path)

        assert ['uv', 'pip', 'install', '--python', str(venv_python),
                '--quiet', '-c', 'constraints.txt', 'setuptools-scm'] in calls

    def test_editable_direct_url_is_local(self, monkeypatch):
        monkeypatch.setattr(us, '_installed_dist_info', lambda _name: {
            'found': True,
            'version': '1.0',
            'direct_url': '{"url":"file:///tmp/pkg","dir_info":{"editable":true}}',
        })

        assert us.installed_source('pkg') == ('local', Path('/tmp/pkg'))

    def test_missing_direct_url_is_index(self, monkeypatch):
        monkeypatch.setattr(us, '_installed_dist_info', lambda _name: {
            'found': True,
            'version': '1.0',
            'direct_url': None,
        })

        assert us.installed_source('pkg') == ('index', None)
