"""Tests for `dev_10x.uv_sync` install-mode flags and extras binding."""

from __future__ import annotations

from pathlib import Path

import pytest
from core_10x.testlib.strict import need

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
    def test_defaults_to_incremental_quiet(self, monkeypatch):
        monkeypatch.delenv('XX_UV_INSTALL_MODE', raising=False)
        assert uv_sync.install_mode() == 'incremental_quiet'

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
        assert not any('editable.' in a for a in args)  # editable.* settings don't apply to a wheel

    def test_editable_mode_turns_off_rebuild(self, captured_pip_install):
        uv_sync.install_local('py10x-kernel', _pkg(cxx=True), pin=None, mode='editable', verbose=False)
        (args,) = captured_pip_install
        assert '-e' in args
        assert 'py10x-kernel:editable.rebuild=false' in args

    @pytest.mark.parametrize('mode', uv_sync.INSTALL_MODES)
    def test_every_mode_builds_without_isolation_into_the_pyproject_build_dir(self, captured_pip_install, mode):
        # The persistent build-dir comes from the package's pyproject; an isolated build would
        # bake throwaway cmake/ninja paths into its CMakeCache.
        uv_sync.install_local('py10x-kernel', _pkg(cxx=True), pin=None, mode=mode, verbose=False)
        (args,) = captured_pip_install
        assert args[args.index('--no-build-isolation-package') + 1] == 'py10x-kernel'
        assert 'py10x-kernel:cmake.build-type=Release' in args
        assert not any('build-dir' in a for a in args)

    def test_build_type_from_env(self, captured_pip_install, monkeypatch):
        monkeypatch.setenv('XX_UV_BUILD_TYPE', 'Debug')
        uv_sync.install_local('py10x-kernel', _pkg(cxx=True), pin=None, mode='incremental', verbose=False)
        (args,) = captured_pip_install
        assert 'py10x-kernel:cmake.build-type=Debug' in args

    def test_incremental_mode_is_editable_and_verbose(self, captured_pip_install):
        uv_sync.install_local('py10x-kernel', _pkg(cxx=True), pin=None, mode='incremental', verbose=False)
        (args,) = captured_pip_install
        assert '-e' in args
        assert not any('editable.rebuild' in a for a in args)  # pyproject default: on
        assert 'py10x-kernel:editable.verbose=true' in args

    def test_incremental_quiet_mode_uses_pyproject_defaults(self, captured_pip_install):
        # incremental_quiet == the pyproject defaults (rebuild on, verbose off): nothing to override.
        uv_sync.install_local('py10x-kernel', _pkg(cxx=True), pin=None, mode='incremental_quiet', verbose=False)
        (args,) = captured_pip_install
        assert '-e' in args
        assert not any('editable.' in a for a in args)

    @pytest.mark.parametrize('mode', uv_sync.INSTALL_MODES)
    def test_pure_python_package_gets_no_cxx_flags(self, captured_pip_install, mode):
        # Non-cxx packages (py10x-core) never get C++ build flags, regardless of mode.
        uv_sync.install_local('py10x-core', _pkg(cxx=False), pin=None, mode=mode, verbose=False)
        (args,) = captured_pip_install
        assert not any('editable.' in a or 'cmake.' in a for a in args)
        assert '--no-build-isolation-package' not in args

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


class TestInstallDownstreamMemberArgs:
    """Downstream workspace members (fin-base → cxxfin) follow XX_UV_INSTALL_MODE like kernel/infra."""

    @pytest.fixture
    def finbase(self, tmp_path, monkeypatch):
        member = tmp_path / 'cxxfin'
        monkeypatch.setattr(uv_sync, '_workspace_member_paths', lambda _: {'py10x-fin-base-cxx': member})
        monkeypatch.setattr(uv_sync, '_no_build_isolation_packages', lambda _: ['py10x-fin-base-cxx'])
        return member, _pkg(cxx=False, downstream=True, local=tmp_path, subdir='xx_fin')

    def _install(self, captured_pip_install, finbase, mode):
        member, pkg = finbase
        uv_sync.install_local('py10x-fin-base', pkg, pin=None, mode=mode, verbose=False)
        member_args, parent_args = captured_pip_install
        assert str(member) in member_args
        return member_args, parent_args

    @pytest.mark.parametrize('mode', ['incremental', 'incremental_quiet'])
    def test_incremental_member_keeps_pyproject_rebuild(self, captured_pip_install, finbase, mode):
        member_args, parent_args = self._install(captured_pip_install, finbase, mode)
        assert '-e' in member_args
        assert 'py10x-fin-base-cxx:cmake.build-type=Release' in member_args
        # The parent install carries the same member flags, so a transitive rebuild matches.
        assert 'py10x-fin-base-cxx:cmake.build-type=Release' in parent_args
        assert not any('editable.rebuild' in a or 'build-dir' in a for a in member_args + parent_args)

    def test_editable_member_is_plain_editable(self, captured_pip_install, finbase):
        member_args, parent_args = self._install(captured_pip_install, finbase, 'editable')
        assert '-e' in member_args
        assert '--no-build-isolation-package' in member_args
        assert '--no-build-isolation-package' in parent_args
        assert 'py10x-fin-base-cxx:editable.rebuild=false' in member_args
        assert 'py10x-fin-base-cxx:editable.rebuild=false' in parent_args

    def test_normal_member_is_not_editable(self, captured_pip_install, finbase):
        member_args, _ = self._install(captured_pip_install, finbase, 'normal')
        assert '-e' not in member_args
        assert not any('editable.rebuild' in a for a in member_args)


class TestModeToggle:
    def test_toggle_reinstalls_up_to_date_downstream_with_native_members(self, monkeypatch, tmp_path):
        installed = []
        monkeypatch.setattr(uv_sync, 'need_install', lambda *a, **k: False)
        monkeypatch.setattr(uv_sync, '_no_build_isolation_packages', lambda _: ['py10x-fin-base-cxx'])
        monkeypatch.setattr(uv_sync, 'install_local', lambda name, *a, **k: installed.append(name))
        pkgs = {'py10x-fin-base': _pkg(cxx=False, downstream=True, local=tmp_path, subdir='xx_fin')}
        uv_sync.sync_siblings('main', 'editable', None, {'py10x-fin-base': 'local'}, pkgs, ['py10x-fin-base'], True, False)
        assert installed == ['py10x-fin-base']


class TestNoInjectedToolsetPin:
    """The Windows MSVC toolset pin lives in each package's pyproject, never in uv-sync flags."""

    @pytest.mark.parametrize('mode', uv_sync.INSTALL_MODES)
    def test_local_install_passes_no_cmake_args(self, captured_pip_install, monkeypatch, mode):
        monkeypatch.setattr(uv_sync.sys, 'platform', 'win32')
        uv_sync.install_local('py10x-kernel', _pkg(cxx=True), pin=None, mode=mode, verbose=False)
        (args,) = captured_pip_install
        assert not any('cmake.args' in a for a in args)


class TestInstallGitArgs:
    def test_git_cxx_install_uses_throwaway_build_dir(self, captured_pip_install):
        # Isolated build from uv's git checkout: the pyproject's persistent build-dir is cleared.
        uv_sync.install_git('py10x-kernel', _pkg(cxx=True), 'main')
        (args,) = captured_pip_install
        assert 'py10x-kernel:build-dir=' in args
        assert 'py10x-kernel:editable.rebuild=false' in args  # rebuild needs a persistent build-dir
        assert '--no-build-isolation-package' not in args

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
        # uv_sync() reads PROJECT_ROOT / 'pyproject.toml' (via _dev10x_cfg) unmocked below; that's
        # only present in a py10x source checkout, not when core is installed as a wheel (sibling
        # wheel CI runs this suite from site-packages with no source pyproject nearby).
        need((uv_sync.PROJECT_ROOT / 'pyproject.toml').is_file(), 'py10x source checkout (no source pyproject when core is installed as a wheel)')
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
        """Siblings are in-tree, so py10x-dev builds them locally (same as legacy py10x-core-dev)."""
        uv_sync.uv_sync('py10x-dev', '--all-extras', '--with-downstream')
        assert not any('git+' in a for c in isolated_sync for a in c)
        sibling = [c for c in isolated_sync if any(str(Path('/cxx10x/core_10x')) == a or str(Path('/cxx10x/infra_10x')) == a for a in c)]
        assert sibling
        for args in sibling:
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
