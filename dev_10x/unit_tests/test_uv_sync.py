"""Tests for `dev_10x.uv_sync`'s XX_UV_INSTALL_MODE handling."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev_10x import uv_sync


@pytest.fixture
def captured_pip_install(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(uv_sync, '_pip_install', lambda *args: calls.append(list(args)))
    return calls


def _pkg(cxx: bool) -> dict:
    return {'local': Path('/cxx10x/core_10x'), 'cxx': cxx, 'downstream': False}


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
