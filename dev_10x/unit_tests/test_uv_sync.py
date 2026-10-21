"""Tests for `dev_10x.uv_sync` install-mode flags and extras binding."""

from __future__ import annotations

from pathlib import Path

import pytest
from core_10x.testlib.strict import need

from dev_10x import uv_sync


@pytest.fixture(autouse=True)
def _installed_in_mode(monkeypatch):
    """By default the installed C++ packages match the requested mode (no real venv is inspected)."""
    monkeypatch.setattr(uv_sync, '_mode_mismatch', lambda *a, **k: [])


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
    def test_every_mode_leaves_build_dir_type_and_isolation_to_pyproject(self, captured_pip_install, mode):
        # build-dir / cmake.build-type come from the package's pyproject (override via SKBUILD_* env),
        # no-build-isolation from the root's [tool.uv].
        uv_sync.install_local('py10x-kernel', _pkg(cxx=True), pin=None, mode=mode, verbose=False)
        (args,) = captured_pip_install
        assert not any('build-dir' in a or 'cmake.build-type' in a for a in args)
        assert '--no-build-isolation-package' not in args

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
        monkeypatch.setattr(uv_sync, '_native_members', lambda _: {'py10x-fin-base-cxx': member})
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
        # incremental_quiet == pyproject defaults; incremental only turns the rebuild log on.
        assert not any('editable.rebuild' in a or 'build-dir' in a for a in member_args + parent_args)
        if mode == 'incremental':
            # The parent install carries the same member flags, so a transitive rebuild matches.
            assert 'py10x-fin-base-cxx:editable.verbose=true' in member_args
            assert 'py10x-fin-base-cxx:editable.verbose=true' in parent_args

    def test_editable_member_is_plain_editable(self, captured_pip_install, finbase):
        member_args, parent_args = self._install(captured_pip_install, finbase, 'editable')
        assert '-e' in member_args
        assert 'py10x-fin-base-cxx:editable.rebuild=false' in member_args
        assert 'py10x-fin-base-cxx:editable.rebuild=false' in parent_args

    def test_normal_member_is_not_editable(self, captured_pip_install, finbase):
        member_args, _ = self._install(captured_pip_install, finbase, 'normal')
        assert '-e' not in member_args
        assert not any('editable.rebuild' in a for a in member_args)


class TestNoBuildIsolationLists:
    """Every local C++ package sets a persistent build-dir, which an isolated build would poison
    (throwaway cmake/ninja paths baked into its CMakeCache). So each must be in
    1) the root pyproject's `[tool.uv] no-build-isolation-package` (what uv-sync's `uv pip install`
       reads), and
    2) the list of every enclosing package it lives under (e.g. xx_fin for xx_fin/cxxfin), which
       covers a plain `uv sync` run inside that package."""

    ROOT = Path(uv_sync.__file__).resolve().parents[1]

    @staticmethod
    def _pyproject(path: Path) -> dict:
        import tomllib

        return tomllib.loads((path / 'pyproject.toml').read_text(encoding='utf-8'))

    @classmethod
    def _listed(cls, path: Path) -> set[str]:
        return set(cls._pyproject(path).get('tool', {}).get('uv', {}).get('no-build-isolation-package', []))

    @classmethod
    def _cxx_packages(cls) -> dict[str, Path]:
        cfg = cls._pyproject(cls.ROOT)['tool']['dev_10x']
        out = {name: (cls.ROOT / spec['path']).resolve() for name, spec in cfg['siblings'].items()}
        for spec in cfg.get('downstream', {}).values():
            out |= uv_sync._native_members(cls.ROOT / spec['path'])
        return out

    def test_discovers_the_known_cxx_packages(self):
        cxx = self._cxx_packages()
        assert {'py10x-kernel', 'py10x-infra', 'py10x-fin-base-cxx'} <= cxx.keys()
        assert all(uv_sync._is_native(path) for path in cxx.values())

    def test_root_lists_every_cxx_package(self):
        missing = self._cxx_packages().keys() - self._listed(self.ROOT)
        assert not missing, f'add to {self.ROOT / "pyproject.toml"} [tool.uv] no-build-isolation-package: {sorted(missing)}'

    def test_enclosing_packages_list_their_cxx_subpackages(self):
        problems = []
        for name, path in self._cxx_packages().items():
            for parent in path.parents:
                if parent == self.ROOT or self.ROOT not in parent.parents:
                    break
                if (parent / 'pyproject.toml').is_file() and name not in self._listed(parent):
                    problems.append(f'{parent / "pyproject.toml"}: add {name}')
        assert not problems, '[tool.uv] no-build-isolation-package missing: ' + '; '.join(problems)

    def test_every_cxx_package_sets_local_build_defaults(self):
        for name, path in self._cxx_packages().items():
            skb = self._pyproject(path)['tool']['scikit-build']
            assert {'build-dir', 'editable', 'cmake'} <= skb.keys(), name
            assert skb['cmake']['build-type'] and skb['editable']['rebuild'], name

    def test_local_builds_are_debug_and_published_wheels_release(self):
        # Development default is Debug; cibuildwheel (what ships to PyPI) must stay Release.
        for name, path in self._cxx_packages().items():
            tool = self._pyproject(path)['tool']
            assert tool['scikit-build']['cmake']['build-type'] == 'Debug', name
            assert tool['cibuildwheel']['config-settings']['cmake.build-type'] == 'Release', name


class TestNativeMembers:
    def test_only_scikit_build_members(self, tmp_path):
        (tmp_path / 'pyproject.toml').write_text('[tool.uv.workspace]\nmembers = ["*"]\n')
        for name, backend in (('cpp', 'scikit_build_core.build'), ('py', 'hatchling.build')):
            (tmp_path / name).mkdir()
            (tmp_path / name / 'pyproject.toml').write_text(f'[project]\nname = "{name}"\n[build-system]\nbuild-backend = "{backend}"\n')
        assert uv_sync._native_members(tmp_path) == {'cpp': (tmp_path / 'cpp').resolve()}


class TestModeToggle:
    def test_toggle_reinstalls_up_to_date_downstream_with_native_members(self, monkeypatch, tmp_path):
        installed = []
        monkeypatch.setattr(uv_sync, 'need_install', lambda *a, **k: False)
        monkeypatch.setattr(uv_sync, '_native_members', lambda _: {'py10x-fin-base-cxx': tmp_path / 'cxxfin'})
        monkeypatch.setattr(uv_sync, 'install_local', lambda name, *a, **k: installed.append(name))
        pkgs = {'py10x-fin-base': _pkg(cxx=False, downstream=True, local=tmp_path, subdir='xx_fin')}
        uv_sync.sync_siblings('main', 'editable', None, {'py10x-fin-base': 'local'}, pkgs, ['py10x-fin-base'], True, False)
        assert installed == ['py10x-fin-base']


class TestModeMismatch:
    def test_installed_for_another_mode_reinstalls_in_order(self, monkeypatch, tmp_path):
        """Up to date by version, but installed for another mode (e.g. by `./xx-build init`): siblings are
        reinstalled one by one before the downstream, never all in the downstream's install."""
        installed = []
        monkeypatch.setattr(uv_sync, 'need_install', lambda *a, **k: False)
        monkeypatch.setattr(uv_sync, '_native_members', lambda src: {'py10x-fin-base-cxx': tmp_path / 'cxxfin'} if Path(src) == tmp_path else {})
        monkeypatch.setattr(uv_sync, '_mode_mismatch', lambda name, pkg, mode: [f'{name}: expected rebuild=False, got True'])
        monkeypatch.setattr(uv_sync, 'install_local', lambda name, *a, **k: installed.append(name))
        pkgs = {
            'py10x-kernel': _pkg(cxx=True),
            'py10x-fin-base': _pkg(cxx=False, downstream=True, local=tmp_path, subdir='xx_fin'),
        }
        kinds = dict.fromkeys(pkgs, 'local')
        uv_sync.sync_siblings('main', 'editable', None, kinds, pkgs, list(pkgs), False, False)
        assert installed == ['py10x-kernel', 'py10x-fin-base']

    def test_matching_mode_is_left_alone(self, monkeypatch):
        installed = []
        monkeypatch.setattr(uv_sync, 'need_install', lambda *a, **k: False)
        monkeypatch.setattr(uv_sync, 'install_local', lambda name, *a, **k: installed.append(name))
        uv_sync.sync_siblings('main', 'editable', None, {'py10x-kernel': 'local'}, {'py10x-kernel': _pkg(cxx=True)}, ['py10x-kernel'], False, False)
        assert installed == []


class TestInstallState:
    def test_tracks_build_type_override(self, monkeypatch):
        monkeypatch.delenv('SKBUILD_CMAKE_BUILD_TYPE', raising=False)
        assert uv_sync.install_state('editable') == 'editable:default'
        monkeypatch.setenv('SKBUILD_CMAKE_BUILD_TYPE', 'Debug')
        assert uv_sync.install_state('editable') == 'editable:Debug'

    def test_reads_legacy_mode_only_marker(self, tmp_path):
        (tmp_path / '.venv').mkdir()
        uv_sync._install_mode_marker(tmp_path).write_text('incremental_quiet')
        assert uv_sync.read_install_mode_state(tmp_path) == 'incremental_quiet:default'

    def test_round_trip(self, tmp_path):
        (tmp_path / '.venv').mkdir()
        uv_sync.persist_install_mode_state(tmp_path, 'normal:Release')
        assert uv_sync.read_install_mode_state(tmp_path) == 'normal:Release'


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
        monkeypatch.setattr(uv_sync, '_native_members', lambda src: {})
        return captured_pip_install

    @staticmethod
    def _requirements_calls(calls: list[list[str]]) -> list[list[str]]:
        return [c for c in calls if '--requirements' in c and 'pyproject.toml' in c]

    @staticmethod
    def _non_requirements_calls(calls: list[list[str]]) -> list[list[str]]:
        return [c for c in calls if not ('--requirements' in c and 'pyproject.toml' in c)]

    def test_root_sources_off_for_siblings_only_where_core_deps_resolve(self, isolated_sync):
        """The root's editable kernel/infra sources must not override uv-sync's choice of source
        (e.g. XX_UV_INSTALL_MODE=normal); the flag stays off the downstream install (uv quirk)."""
        uv_sync.uv_sync('py10x-dev', '--all-extras', '--with-downstream')

        def no_sources(args):
            return {args[i + 1] for i, a in enumerate(args) if a == '--no-sources-package'}

        core_deps = [c for c in isolated_sync if 'pyproject.toml' in c or ('-e' in c and str(Path('/py10x')) in c)]
        assert len(core_deps) == 2
        assert all(no_sources(c) == {'py10x-kernel', 'py10x-infra'} for c in core_deps)
        assert all(not no_sources(c) for c in isolated_sync if c not in core_deps)

    @pytest.mark.parametrize(
        ('mode', 'expected'), [('editable', 'editable.rebuild=false'), ('normal', 'editable.rebuild=false'), ('incremental', 'editable.verbose=true')]
    )
    def test_downstream_install_carries_the_siblings_mode_flags(self, isolated_sync, monkeypatch, mode, expected):
        """The downstream install rebuilds the siblings through the root's editable sources (uv); they must
        keep their mode's settings, e.g. no rebuild-on-import in 'editable' mode (Windows xdist race)."""
        monkeypatch.setenv('XX_UV_INSTALL_MODE', mode)
        uv_sync.uv_sync('py10x-dev', '--all-extras', '--with-downstream')
        (downstream,) = [c for c in isolated_sync if str(Path('/py10x/xx_fin')) in c]
        settings = {downstream[i + 1] for i, a in enumerate(downstream) if a == '--config-settings-package'}
        assert settings == {f'py10x-kernel:{expected}', f'py10x-infra:{expected}'}

    def test_already_installed_downstream_still_gets_its_members_mode_flags(self, isolated_sync, monkeypatch):
        """Nothing to reinstall (e.g. a venv from `./xx-build init`): the extras-only downstream install must
        still carry cxxfin's (and the siblings') mode flags, or cxxfin keeps the previous mode's settings."""
        monkeypatch.setenv('XX_UV_INSTALL_MODE', 'editable')
        monkeypatch.setattr(uv_sync, 'need_install', lambda *a, **k: False)
        monkeypatch.setattr(
            uv_sync, '_native_members', lambda src: {'py10x-fin-base-cxx': Path(src) / 'cxxfin'} if Path(src).name == 'xx_fin' else {}
        )
        uv_sync.uv_sync('py10x-dev', '--all-extras', '--with-downstream')
        (downstream,) = [c for c in isolated_sync if str(Path('/py10x/xx_fin')) in c]
        settings = {downstream[i + 1] for i, a in enumerate(downstream) if a == '--config-settings-package'}
        assert settings == {f'{n}:editable.rebuild=false' for n in ('py10x-fin-base-cxx', 'py10x-kernel', 'py10x-infra')}

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


class TestClearedVenv:
    """After `.venv` is cleared (e.g. `uv venv --clear`), incremental uv-sync must rebuild every local
    package from source: the build dirs lived in the old `.venv`, so a cached wheel from uv's cache
    would point at a deleted build dir. `--reinstall-package` (implies a refresh) prevents that."""

    LOCAL = {
        uv_sync.CORE: Path('/py10x'),
        'py10x-kernel': Path('/py10x/cxx10x/core_10x'),
        'py10x-infra': Path('/py10x/cxx10x/infra_10x'),
        'py10x-fin-base': Path('/py10x/xx_fin'),
        'py10x-fin-base-cxx': Path('/py10x/xx_fin/cxxfin'),
    }

    @pytest.fixture
    def cleared_sync(self, monkeypatch, captured_pip_install):
        need((uv_sync.PROJECT_ROOT / 'pyproject.toml').is_file(), 'py10x source checkout (no source pyproject when core is installed as a wheel)')
        local = self.LOCAL
        pkgs = {
            uv_sync.CORE: _pkg(cxx=False, local=local[uv_sync.CORE], git='https://example.com/py10x.git', subdir=None),
            'py10x-kernel': _pkg(cxx=True, local=local['py10x-kernel']),
            'py10x-infra': _pkg(cxx=True, local=local['py10x-infra'], subdir='infra_10x'),
            'py10x-fin-base': _pkg(cxx=False, downstream=True, local=local['py10x-fin-base'], subdir='xx_fin'),
        }

        calls = captured_pip_install

        class ClearedVenv:  # starts empty (freshly cleared .venv), then holds what uv-sync installed
            def installed_source(self, name):
                src = str(local[name])
                done = any('-e' in c and c[c.index('-e') + 1] == src and f'--reinstall-package={name}' in c for c in calls)
                return ('local', local[name]) if done else (None, None)

            def installed_version(self, name):
                raise AssertionError(f'{name}: version check on a cleared venv - nothing should be up to date')

        monkeypatch.setenv('XX_UV_INSTALL_MODE', 'incremental_quiet')
        monkeypatch.setattr(uv_sync, 'packages', lambda tomlkit: pkgs)
        monkeypatch.setattr(uv_sync, '_installed_source_helpers', lambda root: ClearedVenv())
        monkeypatch.setattr(uv_sync, 'read_install_mode_state', lambda root: None)  # marker went with the venv
        monkeypatch.setattr(uv_sync, 'persist_install_mode_state', lambda *a, **k: None)
        monkeypatch.setattr(uv_sync, 'persist_profile', lambda *a, **k: None)
        monkeypatch.setattr(uv_sync, '_sibling_pin', lambda name: None)
        monkeypatch.setattr(
            uv_sync,
            '_native_members',
            lambda src: {'py10x-fin-base-cxx': local['py10x-fin-base-cxx']} if Path(src) == local['py10x-fin-base'] else {},
        )
        uv_sync.uv_sync('py10x-dev', '--with-downstream')
        return captured_pip_install

    def _install_of(self, calls, name):
        src = str(self.LOCAL[name])
        matches = [c for c in calls if '-e' in c and c[c.index('-e') + 1] == src]
        assert matches, f'{name}: no editable install from {src}'
        return matches[0]

    @pytest.mark.parametrize('name', list(LOCAL))
    def test_every_local_package_is_rebuilt_from_source(self, cleared_sync, name):
        assert f'--reinstall-package={name}' in self._install_of(cleared_sync, name)

    @pytest.mark.parametrize('name', ['py10x-kernel', 'py10x-infra', 'py10x-fin-base-cxx'])
    def test_cxx_packages_keep_rebuild_on_import(self, cleared_sync, name):
        args = self._install_of(cleared_sync, name)
        assert f'{name}:editable.rebuild=false' not in args
        assert f'{name}:build-dir=' not in ' '.join(args)  # pyproject's persistent .venv build dir


class TestWindowsToolsetPin:
    """Every C++ (scikit-build-core) package in the repo pins the MSVC toolset py10x requires on
    Windows (Py10xMsvcVersion.cmake), in its own pyproject: nothing else passes it any more."""

    ROOT = Path(uv_sync.__file__).resolve().parents[1]

    def test_every_scikit_build_pyproject_pins_the_toolset(self):
        import tomllib

        need((self.ROOT / 'pyproject.toml').is_file(), 'py10x source checkout')
        skip = {'.venv', '.git', '.claude', 'node_modules', '_deps'}
        found, missing = [], []
        for pyproject in sorted(self.ROOT.rglob('pyproject.toml')):
            if skip & set(pyproject.relative_to(self.ROOT).parts):
                continue
            if not uv_sync._is_native(pyproject.parent):
                continue
            found.append(pyproject)
            overrides = tomllib.loads(pyproject.read_text(encoding='utf-8')).get('tool', {}).get('scikit-build', {}).get('overrides', [])
            if not any(o.get('if', {}).get('platform-system') == '^win' and '-T' in o.get('cmake', {}).get('args', []) for o in overrides):
                missing.append(str(pyproject.relative_to(self.ROOT)))
        assert len(found) >= 4, found  # kernel, infra, cxxfin, cross_module_test
        assert not missing, f'add the Windows [[tool.scikit-build.overrides]] toolset pin to: {missing}'
