"""`dev_10x.env_check`: loader parsing and per-mode expectations (the CI install-mode guard)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dev_10x import env_check

SRC = Path('/repo/cxx10x/core_10x').resolve()  # absolute on Windows too (drive letter), for as_uri()


def _loader(tmp_path: Path, path: str | None, rebuild: bool, verbose: bool) -> Path:
    loader = tmp_path / '_py10x_kernel_editable.py'
    loader.write_text(
        f"def install(*args): pass\n\n\ninstall({{}}, {{'py10x_kernel': 'py10x_kernel.pyi'}}, {path!r}, {rebuild}, {verbose}, [], [], '')\n",
        encoding='utf-8',
    )
    return loader


def _state(*, editable: bool = True, rebuild: bool = True, verbose: bool = False, build_type: str = 'Debug', url: str | None = None) -> dict:
    state = {'url': url or SRC.as_uri(), 'editable': editable, 'local': True}
    if editable:
        state.update(rebuild=rebuild, verbose=verbose, build_type=build_type)
    return state


@pytest.fixture(autouse=True)
def _debug_build_type(monkeypatch):
    monkeypatch.setenv('SKBUILD_CMAKE_BUILD_TYPE', 'Debug')


class TestLoaderSettings:
    def test_reads_rebuild_verbose_and_build_type(self, tmp_path):
        loader = _loader(tmp_path, '/repo/build/py10x-build/py10x-kernel/Release/cp312-cp312-linux_x86_64', False, True)
        build_dir = '/repo/build/py10x-build/py10x-kernel/Release/cp312-cp312-linux_x86_64'
        assert env_check.loader_settings(loader) == {'rebuild': False, 'verbose': True, 'build_type': 'Release', 'build_dir': build_dir}

    def test_windows_build_dir(self, tmp_path):
        loader = _loader(tmp_path, r'D:\a\py10x\build\py10x-build\py10x-infra\Debug\cp313-cp313-win_amd64', True, False)
        assert env_check.loader_settings(loader)['build_type'] == 'Debug'

    def test_no_build_dir(self, tmp_path):
        assert env_check.loader_settings(_loader(tmp_path, None, False, False))['build_type'] is None


class TestCheckCxx:
    @pytest.mark.parametrize(
        ('mode', 'state'),
        [
            ('dev', _state(rebuild=True, verbose=False)),
            ('dev-release', _state(rebuild=True, verbose=False, build_type='Release')),
            ('ci-release', _state(rebuild=False, build_type='Release')),
            ('ci-release', _state(rebuild=False, verbose=True, build_type='Release')),  # verbose is not part of ci-release
        ],
    )
    def test_expected_state_passes(self, mode, state):
        assert env_check.check_cxx('py10x-kernel', state, SRC, env_check.MODES[mode]) == []

    @pytest.mark.parametrize(
        ('mode', 'state', 'problem'),
        [
            # The 3a regressions: root sources overriding the install mode (Docker: a rebuild-on-import
            # install with its build dir gone), and the downstream install turning rebuild-on-import back
            # on in CI (the Windows xdist race).
            ('ci-release', _state(rebuild=True, build_type='Release'), 'expected rebuild=False'),
            ('ci-release', _state(editable=False), 'expected editable'),
            ('dev', _state(rebuild=True, verbose=True), 'expected verbose=False'),
            ('dev', _state(build_type='Release'), 'expected build type Debug'),
            ('dev-release', _state(build_type='Debug'), 'expected build type Release'),
            ('ci-release', _state(rebuild=False, build_type='Release', url='file:///elsewhere/core_10x'), 'expected an install from'),
        ],
    )
    def test_wrong_state_is_reported(self, mode, state, problem):
        problems = env_check.check_cxx('py10x-kernel', state, SRC, env_check.MODES[mode])
        assert len(problems) == 1 and problem in problems[0]

    def test_index_install_is_reported(self):
        state = {'url': None, 'editable': True, 'local': False}
        assert 'the index' in env_check.check_cxx('py10x-kernel', state, SRC, env_check.MODES['dev'])[0]

    def test_missing_package_is_reported(self):
        assert env_check.check_cxx('py10x-kernel', None, SRC, env_check.MODES['dev']) == ['py10x-kernel: not installed']


class TestModes:
    def test_uv_sync_install_modes_map_like_uv_sync(self):
        from dev_10x import uv_sync

        assert env_check.ALIASES == uv_sync.MODES

    @pytest.mark.parametrize(
        ('env', 'uv_toml_mode', 'expected'), [('editable', 'dev-release', 'editable'), (None, 'dev-release', 'dev-release'), (None, None, 'dev')]
    )
    def test_default_mode(self, monkeypatch, tmp_path, env, uv_toml_mode, expected):
        """$XX_UV_INSTALL_MODE (uv-sync), else the mode `./xx-build set-mode` left in uv.toml, else dev."""
        from dev_10x import xx_build

        if env:
            monkeypatch.setenv('XX_UV_INSTALL_MODE', env)
        else:
            monkeypatch.delenv('XX_UV_INSTALL_MODE', raising=False)
        if uv_toml_mode:
            (tmp_path / 'uv.toml').write_text(xx_build.HEADER.format(mode=uv_toml_mode), encoding='utf-8')
        assert env_check.default_mode(tmp_path) == expected

    def test_main_checks_the_default_mode(self, monkeypatch):
        seen = {}
        monkeypatch.setenv('XX_UV_INSTALL_MODE', 'editable')
        monkeypatch.setattr(env_check, 'check', lambda mode, downstream: (seen.update(mode=mode), ([], []))[1])
        assert env_check.main(['--no-import']) == 0
        assert seen == {'mode': 'editable'}


class TestImportModules:
    def test_core_10x_first_then_compiled_modules(self, monkeypatch):
        """core_10x promotes the kernel to RTLD_GLOBAL; importing cxxfin before it fails on Linux."""
        imported = []
        monkeypatch.setattr(env_check.importlib, 'import_module', imported.append)
        monkeypatch.setattr(env_check, 'first_party', lambda root: ({'py10x-kernel': SRC}, {}, {'py10x-fin-base-cxx': SRC}))
        assert env_check.import_modules(downstream=True) == []
        assert imported == ['core_10x', 'py10x_kernel', 'cxxfin']


class TestSkipEditableRebuilds:
    """dev_10x.pytest_plugin: rebuild once in the main process, then workers/subprocesses skip the check."""

    def test_imports_rebuild_on_import_packages_then_lists_their_build_dirs(self, monkeypatch):
        from dev_10x import pytest_plugin

        imported = []
        states = {
            'py10x-kernel': {'rebuild': True, 'build_dir': '/b/kernel'},
            'py10x-infra': {'rebuild': False, 'build_dir': '/b/infra'},  # 'editable' mode: nothing to skip
            'py10x-fin-base-cxx': {'rebuild': True, 'build_dir': '/b/cxxfin'},
        }
        monkeypatch.setattr(env_check, 'first_party', lambda root: ({'py10x-kernel': SRC, 'py10x-infra': SRC}, {}, {'py10x-fin-base-cxx': SRC}))
        monkeypatch.setattr(env_check, 'installed', states.get)
        monkeypatch.setattr('importlib.import_module', imported.append)
        monkeypatch.setenv('SKBUILD_EDITABLE_SKIP', '/already')
        pytest_plugin._skip_editable_rebuilds()
        assert imported == ['py10x_kernel', 'cxxfin']
        assert os.environ['SKBUILD_EDITABLE_SKIP'].split(os.pathsep) == ['/already', '/b/kernel', '/b/cxxfin']

    def test_outside_a_source_checkout_does_nothing(self, monkeypatch):
        from dev_10x import pytest_plugin

        def no_checkout(root):
            raise FileNotFoundError(root)

        monkeypatch.setattr(env_check, 'first_party', no_checkout)
        monkeypatch.delenv('SKBUILD_EDITABLE_SKIP', raising=False)
        pytest_plugin._skip_editable_rebuilds()
        assert 'SKBUILD_EDITABLE_SKIP' not in os.environ
