"""Unit tests for pure helpers in `dev_10x.uv_sync`."""
from __future__ import annotations

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


class TestUvSyncCoreInstall:
    @staticmethod
    def _pkgs(tmp_path):
        return {
            us.CORE: {'local': tmp_path / 'py10x', 'git': 'https://example.test/py10x.git',
                      'subdir': None, 'cxx': False},
            'py10x-kernel': {'local': tmp_path / 'cxx10x' / 'core_10x',
                             'git': 'https://example.test/cxx10x.git',
                             'subdir': 'core_10x', 'cxx': True},
            'py10x-infra': {'local': tmp_path / 'cxx10x' / 'infra_10x',
                            'git': 'https://example.test/cxx10x.git',
                            'subdir': 'infra_10x', 'cxx': True},
        }

    def test_local_core_install_does_not_resolve_deps(self, monkeypatch, tmp_path):
        calls = []
        pkgs = self._pkgs(tmp_path)

        monkeypatch.setattr(us, 'ensure_env_and_runtime_deps', lambda _root: object())
        monkeypatch.setattr(us, 'packages', lambda _tomlkit: pkgs)
        monkeypatch.setattr(us, '_dev10x_cfg', lambda _tomlkit: {})
        monkeypatch.setattr(us, 'read_incremental_state', lambda _root: None)
        monkeypatch.setattr(us, '_pip_install', lambda *args: calls.append(('pip', args)))
        monkeypatch.setattr(us, 'installed_source', lambda _name: ('local', None))
        monkeypatch.setattr(us, 'need_install', lambda name, *_args, **_kwargs: name == us.CORE)
        monkeypatch.setattr(us, 'persist_profile', lambda *_args: None)
        monkeypatch.setattr(us, 'persist_incremental_state', lambda *_args: None)

        def fake_install_local(name, pkg, incremental, verbose, *, no_deps=False):
            calls.append(('local', name, incremental, verbose, no_deps))

        monkeypatch.setattr(us, 'install_local', fake_install_local)

        us.uv_sync('py10x-core-dev', '--all-extras')

        assert ('local', us.CORE, False, False, True) in calls

    def test_git_core_install_does_not_resolve_deps(self, monkeypatch, tmp_path):
        calls = []
        pkgs = self._pkgs(tmp_path)

        monkeypatch.setattr(us, 'ensure_env_and_runtime_deps', lambda _root: object())
        monkeypatch.setattr(us, 'packages', lambda _tomlkit: pkgs)
        monkeypatch.setattr(us, '_dev10x_cfg', lambda _tomlkit: {})
        monkeypatch.setattr(us, 'read_incremental_state', lambda _root: None)
        monkeypatch.setattr(us, '_pip_install', lambda *args: calls.append(('pip', args)))
        monkeypatch.setattr(us, 'installed_source', lambda _name: ('other', None))
        monkeypatch.setattr(us, 'need_install', lambda *_args, **_kwargs: False)
        monkeypatch.setattr(us, 'install_local', lambda *args, **kwargs: None)
        monkeypatch.setattr(us, 'persist_profile', lambda *_args: None)
        monkeypatch.setattr(us, 'persist_incremental_state', lambda *_args: None)

        def fake_install_git(name, pkg, branch, *, no_deps=False):
            calls.append(('git', name, branch, no_deps))

        monkeypatch.setattr(us, 'install_git', fake_install_git)

        us.uv_sync('domain-dev')

        assert ('git', us.CORE, 'main', True) in calls
