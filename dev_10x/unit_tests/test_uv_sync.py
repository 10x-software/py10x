"""Tests for `dev_10x.uv_sync` install-mode flags and extras binding."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev_10x import uv_sync


@pytest.fixture
def captured_pip_install(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(uv_sync, '_pip_install', lambda *args: calls.append(list(args)))
    return calls


def _pkg(
    cxx: bool, *, downstream: bool = False, local: Path | None = None, git: str = 'https://example.com/cxx10x.git', subdir: str | None = 'core_10x'
) -> dict:
    return {
        'local': local or Path('/cxx10x/core_10x'),
        'git': git,
        'subdir': subdir,
        'cxx': cxx,
        'downstream': downstream,
    }


def _has_extras(args: list[str]) -> bool:
    return '--all-extras' in args or any(a == '--extra' or a.startswith('--extra=') for a in args)


class TestInstallMode:
    def test_defaults_to_editable(self, monkeypatch):
        monkeypatch.delenv('XX_UV_INSTALL_MODE', raising=False)
        assert uv_sync.install_mode() == 'editable'

    @pytest.mark.parametrize('mode', uv_sync.INSTALL_MODES)
    def test_accepts_every_declared_mode(self, monkeypatch, mode):
        monkeypatch.setenv('XX_UV_INSTALL_MODE', mode)
        assert uv_sync.install_mode() == mode

    def test_rejects_unknown_mode(self, monkeypatch):
        monkeypatch.setenv('XX_UV_INSTALL_MODE', 'bogus')
        with pytest.raises(ValueError, match='XX_UV_INSTALL_MODE'):
            uv_sync.install_mode()


class TestInstallLocalArgs:
    def test_normal_mode_is_not_editable(self, captured_pip_install):
        uv_sync.install_local('py10x-kernel', _pkg(cxx=True), pin=None, mode='normal', verbose=False)
        (args,) = captured_pip_install
        assert '-e' not in args
        assert str(_pkg(cxx=True)['local']) in args
        assert not any('editable.rebuild' in a for a in args)

    def test_editable_mode_is_editable_without_incremental_flags(self, captured_pip_install):
        uv_sync.install_local('py10x-kernel', _pkg(cxx=True), pin=None, mode='editable', verbose=False)
        (args,) = captured_pip_install
        assert '-e' in args
        assert not any('--no-build-isolation-package' == a for a in args)
        assert not any('editable.rebuild' in a for a in args)

    def test_incremental_mode_is_editable_and_verbose(self, captured_pip_install):
        uv_sync.install_local('py10x-kernel', _pkg(cxx=True), pin=None, mode='incremental', verbose=False)
        (args,) = captured_pip_install
        assert '-e' in args
        assert any('editable.rebuild=true' in a for a in args)
        assert any('editable.verbose=true' in a for a in args)

    def test_incremental_quiet_mode_silences_verbose(self, captured_pip_install):
        uv_sync.install_local('py10x-kernel', _pkg(cxx=True), pin=None, mode='incremental_quiet', verbose=False)
        (args,) = captured_pip_install
        assert '-e' in args
        assert any('editable.rebuild=true' in a for a in args)
        assert any('editable.verbose=false' in a for a in args)

    def test_normal_mode_pure_python_package_gets_no_incremental_flags(self, captured_pip_install):
        # Non-cxx packages (py10x-core) never get incremental flags, regardless of mode.
        uv_sync.install_local('py10x-core', _pkg(cxx=False), pin=None, mode='incremental', verbose=False)
        (args,) = captured_pip_install
        assert not any('editable.rebuild' in a for a in args)

    def test_local_sibling_ignores_extras_args(self, captured_pip_install):
        uv_sync.install_local('py10x-kernel', _pkg(cxx=True), pin=None, mode='editable', verbose=False, extras_args=['--all-extras'])
        (args,) = captured_pip_install
        assert not _has_extras(args)
        assert '--requirements' not in args

    def test_local_downstream_forwards_extras(self, captured_pip_install, tmp_path):
        uv_sync.install_local(
            'py10x-fin-base',
            _pkg(cxx=False, downstream=True, local=tmp_path, subdir='xx_fin'),
            pin=None,
            mode='editable',
            verbose=False,
            extras_args=['--all-extras'],
        )
        parent = captured_pip_install[-1]
        assert '--all-extras' in parent
        assert '--requirements' in parent
        assert str(tmp_path / 'pyproject.toml') in parent


class TestInstallGitArgs:
    def test_git_sibling_install_has_no_extras(self, captured_pip_install):
        uv_sync.install_git('py10x-kernel', _pkg(cxx=True), 'main')
        (args,) = captured_pip_install
        assert any('git+' in a and 'py10x-kernel' in a for a in args)
        assert not _has_extras(args)
        assert '--requirements' not in args


class TestPipExtrasArgs:
    def test_extracts_all_extras_and_extra(self):
        assert uv_sync._pip_extras_args(('--all-extras', '--quiet')) == ['--all-extras']
        assert uv_sync._pip_extras_args(('--extra', 'bbg', '--all-extras', '--verbose')) == ['--extra', 'bbg', '--all-extras']
        assert uv_sync._pip_extras_args(('--extra=dev',)) == ['--extra=dev']
        assert uv_sync._pip_extras_args(('--quiet',)) == []


class TestUvSyncExtras:
    """`--all-extras` binds to the current package and to local downstreams, never to siblings."""

    @pytest.fixture
    def isolated_sync(self, monkeypatch, captured_pip_install):
        pkgs = {
            uv_sync.CORE: _pkg(cxx=False, local=Path('/py10x'), git='https://example.com/py10x.git', subdir=None),
            'py10x-kernel': _pkg(cxx=True),
            'py10x-infra': _pkg(cxx=True, local=Path('/cxx10x/infra_10x'), subdir='infra_10x'),
            'py10x-fin-base': _pkg(cxx=False, downstream=True, local=Path('/py10x/xx_fin'), git='https://example.com/py10x.git', subdir='xx_fin'),
        }

        class Installs:
            def installed_source(self, name):
                return ('local', pkgs[name]['local'])

            def installed_version(self, name):
                return '0'

        monkeypatch.setattr(uv_sync, 'packages', lambda tomlkit: pkgs)
        monkeypatch.setattr(uv_sync, 'need_install', lambda *a, **k: True)
        monkeypatch.setattr(uv_sync, 'persist_profile', lambda *a, **k: None)
        monkeypatch.setattr(uv_sync, 'persist_install_mode_state', lambda *a, **k: None)
        monkeypatch.setattr(uv_sync, '_installed_source_helpers', lambda root: Installs())
        monkeypatch.setattr(uv_sync, '_sibling_pin', lambda name: None)
        monkeypatch.setattr(uv_sync, '_no_build_isolation_packages', lambda src: [])
        return captured_pip_install

    @staticmethod
    def _requirements_calls(calls: list[list[str]]) -> list[list[str]]:
        return [c for c in calls if '--requirements' in c and 'pyproject.toml' in c]

    @staticmethod
    def _non_requirements_calls(calls: list[list[str]]) -> list[list[str]]:
        return [c for c in calls if not ('--requirements' in c and 'pyproject.toml' in c)]

    def test_py10x_dev_all_extras_stays_off_siblings(self, isolated_sync):
        uv_sync.uv_sync('py10x-dev', '--all-extras')
        req = self._requirements_calls(isolated_sync)
        assert req and all('--all-extras' in c for c in req)
        for args in self._non_requirements_calls(isolated_sync):
            assert not _has_extras(args), args

    def test_py10x_dev_all_extras_with_downstream_uses_local(self, isolated_sync):
        uv_sync.uv_sync('py10x-dev', '--all-extras', '--with-downstream')
        git_siblings = [c for c in isolated_sync if any('git+' in a and ('py10x-kernel' in a or 'py10x-infra' in a) for a in c)]
        assert git_siblings
        for args in git_siblings:
            assert not _has_extras(args)
        downstream = [c for c in isolated_sync if any(str(Path('/py10x/xx_fin')) == a for a in c)]
        assert downstream
        assert any('--all-extras' in c and '--requirements' in c for c in downstream)
        assert not any('git+' in a and 'py10x-fin-base' in a for c in isolated_sync for a in c)

    def test_py10x_core_dev_all_extras_not_on_local_siblings(self, isolated_sync):
        uv_sync.uv_sync('py10x-core-dev', '--all-extras')
        sibling = [c for c in isolated_sync if any(str(Path('/cxx10x/core_10x')) == a or str(Path('/cxx10x/infra_10x')) == a for a in c)]
        assert sibling
        for args in sibling:
            assert not _has_extras(args)
        req = self._requirements_calls(isolated_sync)
        assert req and all('--all-extras' in c for c in req)

    def test_py10x_core_dev_all_extras_forwards_to_local_downstream(self, isolated_sync):
        uv_sync.uv_sync('py10x-core-dev', '--all-extras', '--with-downstream')
        sibling = [c for c in isolated_sync if any(str(Path('/cxx10x/core_10x')) == a or str(Path('/cxx10x/infra_10x')) == a for a in c)]
        assert sibling
        for args in sibling:
            assert not _has_extras(args)
        downstream = [c for c in isolated_sync if any(str(Path('/py10x/xx_fin')) == a for a in c)]
        assert downstream
        assert any('--all-extras' in c and '--requirements' in c for c in downstream)
        req = self._requirements_calls(isolated_sync)
        assert req and all('--all-extras' in c for c in req)
