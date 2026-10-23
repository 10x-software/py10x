"""Repo configuration of the in-tree C++ (scikit-build-core) packages: no build isolation, local build
defaults, the Windows MSVC toolset pin, and build modes that leave those alone."""

from __future__ import annotations

from pathlib import Path

from core_10x.testlib.strict import need

from dev_10x import env_check


class TestNoBuildIsolationLists:
    """Every local C++ package sets a persistent build-dir, which an isolated build would poison
    (throwaway cmake/ninja paths baked into its CMakeCache). So each must be in
    1) the root pyproject's `[tool.uv] no-build-isolation-package` (what `uv sync` at the root reads), and
    2) the list of every enclosing package it lives under (e.g. xx_fin for xx_fin/cxxfin), which
       covers a plain `uv sync` run inside that package."""

    ROOT = Path(env_check.__file__).resolve().parents[1]

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
            out |= env_check.native_members(cls.ROOT / spec['path'])
        return out

    def test_discovers_the_known_cxx_packages(self):
        cxx = self._cxx_packages()
        assert {'py10x-kernel', 'py10x-infra', 'py10x-fin-base-cxx'} <= cxx.keys()
        assert all(env_check.is_native(path) for path in cxx.values())

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
        assert env_check.native_members(tmp_path) == {'cpp': (tmp_path / 'cpp').resolve()}


class TestWindowsToolsetPin:
    """Every C++ (scikit-build-core) package in the repo pins the MSVC toolset py10x requires on
    Windows (Py10xMsvcVersion.cmake), in its own pyproject: nothing else passes it any more."""

    ROOT = Path(env_check.__file__).resolve().parents[1]

    def test_every_scikit_build_pyproject_pins_the_toolset(self):
        import tomllib

        need((self.ROOT / 'pyproject.toml').is_file(), 'py10x source checkout')
        skip = {'.venv', '.git', '.claude', 'node_modules', '_deps'}
        found, missing = [], []
        for pyproject in sorted(self.ROOT.rglob('pyproject.toml')):
            if skip & set(pyproject.relative_to(self.ROOT).parts):
                continue
            if not env_check.is_native(pyproject.parent):
                continue
            found.append(pyproject)
            overrides = tomllib.loads(pyproject.read_text(encoding='utf-8')).get('tool', {}).get('scikit-build', {}).get('overrides', [])
            if not any(o.get('if', {}).get('platform-system') == '^win' and '-T' in o.get('cmake', {}).get('args', []) for o in overrides):
                missing.append(str(pyproject.relative_to(self.ROOT)))
        assert len(found) >= 4, found  # kernel, infra, cxxfin, cross_module_test
        assert not missing, f'add the Windows [[tool.scikit-build.overrides]] toolset pin to: {missing}'


class TestBuildModes:
    """[tool.dev_10x.modes] only changes build type / rebuild settings - never cmake args (the Windows
    toolset pin stays in each package's pyproject) - and env_check knows every mode."""

    ROOT = Path(env_check.__file__).resolve().parents[1]

    def _modes(self) -> dict:
        import tomllib

        need((self.ROOT / 'pyproject.toml').is_file(), 'py10x source checkout')
        return tomllib.loads((self.ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['tool']['dev_10x']['modes']

    def test_modes_pass_no_cmake_args(self):
        for mode, table in self._modes().items():
            for package, settings in table.get('config-settings-package', {}).items():
                assert not any(key.startswith(('cmake.args', 'cmake.define')) for key in settings), (mode, package)

    def test_env_check_knows_every_mode(self):
        assert set(env_check.MODES) == {'dev', *self._modes()}
