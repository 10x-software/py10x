"""`xx-build`: init (refusal, --clean, command order), build modes (set-mode / show-mode / uv.toml), imports."""

from __future__ import annotations

import ast
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from dev_10x import xx_build


@pytest.fixture
def uv_calls(monkeypatch) -> SimpleNamespace:
    """The commands `init` runs (`.cmds`) and the environment each one gets (`.envs`), without running them."""
    calls = SimpleNamespace(cmds=[], envs=[])

    def fake_run(cmd, cwd=None, env=None, check=False):
        calls.cmds.append(list(cmd))
        calls.envs.append(env)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(xx_build.subprocess, 'run', fake_run)
    return calls


def _imported(nodes) -> set[str]:
    modules = {alias.name.split('.')[0] for node in nodes if isinstance(node, ast.Import) for alias in node.names}
    return modules | {node.module.split('.')[0] for node in nodes if isinstance(node, ast.ImportFrom) and node.module}


def test_imports_only_the_standard_library():
    """It runs before the venv exists (`uv run --no-project --isolated --with tomlkit -m dev_10x.xx_build`):
    stdlib at import; tomlkit (from the wrapper's --with) only inside the uv.toml functions."""
    tree = ast.parse(Path(xx_build.__file__).read_text(encoding='utf-8'))
    stdlib = set(sys.stdlib_module_names) | {'__future__'}
    assert _imported(tree.body) <= stdlib
    assert _imported(ast.walk(tree)) <= stdlib | {'tomlkit'}


def test_init_orders_toolchain_then_kernel_then_everything(tmp_path, uv_calls):
    assert xx_build.init(clean=False, sync_args=['--locked'], root=tmp_path) == 0
    assert uv_calls.cmds == [
        ['uv', 'venv'],
        ['uv', 'sync', '--inexact', '--frozen', '--only-group', 'build'],
        [
            'uv', 'sync', '--inexact', '--no-default-groups', '--group', 'build',
            '--reinstall-package', 'py10x-kernel', '--reinstall-package', 'py10x-infra', '--locked',
        ],
        ['uv', 'sync', '--reinstall-package', 'py10x-fin-base-cxx', '--locked'],
    ]  # fmt: skip


@pytest.mark.parametrize('existing', ['.venv', 'build'])
def test_init_refuses_an_existing_environment(tmp_path, uv_calls, capsys, existing):
    (tmp_path / existing).mkdir()
    assert xx_build.init(clean=False, sync_args=[], root=tmp_path) == 1
    assert uv_calls.cmds == []
    assert '--clean' in capsys.readouterr().err


def test_init_clean_deletes_venv_and_build_then_runs(tmp_path, uv_calls):
    for name in ('.venv', 'build'):
        (tmp_path / name / 'sub').mkdir(parents=True)
    assert xx_build.init(clean=True, sync_args=[], root=tmp_path) == 0
    assert not (tmp_path / '.venv').exists()
    assert not (tmp_path / 'build').exists()
    assert len(uv_calls.cmds) == 4


def test_init_clean_unknown_mode_keeps_the_environment(repo, uv_calls):
    """`init --clean --mode <typo>` must fail before .venv and build/ are removed (main exits 2)."""
    for name in ('.venv', 'build'):
        (repo / name).mkdir()
    with pytest.raises(ValueError, match="unknown build mode 'not-a-mode'"):
        xx_build.init(clean=True, sync_args=[], root=repo, mode='not-a-mode')
    assert (repo / '.venv').is_dir() and (repo / 'build').is_dir()
    assert uv_calls.cmds == []


def test_init_stops_at_the_first_failing_step(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, cwd=None, env=None, check=False):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 3 if len(calls) == 2 else 0)

    monkeypatch.setattr(xx_build.subprocess, 'run', fake_run)
    assert xx_build.init(clean=False, sync_args=[], root=tmp_path) == 3
    assert len(calls) == 2


def test_main_parses_init_and_forwards_the_rest(monkeypatch):
    seen = {}
    monkeypatch.setattr(xx_build, 'init', lambda clean, sync_args, mode=None: seen.update(clean=clean, args=sync_args, mode=mode) or 0)
    assert xx_build.main(['init', '--clean', '--mode', 'ci-release', '--locked', '--no-group', 'test']) == 0
    assert seen == {'clean': True, 'args': ['--locked', '--no-group', 'test'], 'mode': 'ci-release'}
    assert xx_build.main(['init', '--mode']) == 2
    assert xx_build.main(['bogus']) == 2


def test_main_parses_set_mode_and_show_mode(monkeypatch):
    seen = []
    monkeypatch.setattr(xx_build, 'set_mode', lambda mode, sync_args: seen.append((mode, sync_args)) or 0)
    monkeypatch.setattr(xx_build, 'show_mode', lambda: seen.append('show') or 0)
    assert xx_build.main(['set-mode', 'dev-release', '--locked']) == 0
    assert xx_build.main(['show-mode']) == 0
    assert seen == [('dev-release', ['--locked']), 'show']
    assert xx_build.main(['set-mode']) == 2


def test_main_rebuild_is_set_mode_with_the_active_mode(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(xx_build, 'set_mode', lambda mode, sync_args: seen.append((mode, sync_args)) or 0)
    monkeypatch.setattr(xx_build, 'active_mode', lambda: 'dev-release')
    assert xx_build.main(['rebuild', '--locked']) == 0
    assert seen == [('dev-release', ['--locked'])]
    monkeypatch.setattr(xx_build, 'active_mode', lambda: None)  # a uv.toml xx-build did not write
    assert xx_build.main(['rebuild']) == 2
    assert 'not written by xx-build' in capsys.readouterr().err
    assert len(seen) == 1


def test_wrapper_runs_isolated_without_the_project():
    root = Path(__file__).resolve().parents[2]
    wrapper = root / 'xx-build'
    if not wrapper.is_file():
        pytest.skip('repo-root wrapper not present (installed-package test run)')
    text = wrapper.read_text(encoding='utf-8')
    assert '\r' not in text
    assert 'uv run --no-project --isolated --with tomlkit -m dev_10x.xx_build "$@"' in text


def test_inner_uv_calls_drop_the_wrappers_virtual_env(tmp_path, uv_calls, monkeypatch):
    """`./xx-build`'s isolated `uv run` sets VIRTUAL_ENV; passing it on makes uv warn on every call."""
    monkeypatch.setenv('VIRTUAL_ENV', str(tmp_path / 'uv-cache-env'))
    assert xx_build.init(clean=False, sync_args=[], root=tmp_path) == 0
    assert uv_calls.envs and all(env is not None and 'VIRTUAL_ENV' not in env for env in uv_calls.envs)


def test_clean_removes_read_only_files(tmp_path, uv_calls):
    """Git pack files from CMake FetchContent are read-only; Windows rmtree cannot delete them as is."""
    pack = tmp_path / 'build' / 'py10x-build' / '_deps' / 'backward-src' / '.git' / 'objects' / 'pack' / 'pack-1.idx'
    pack.parent.mkdir(parents=True)
    pack.write_bytes(b'x')
    pack.chmod(stat.S_IREAD)
    assert xx_build.init(clean=True, sync_args=[], root=tmp_path) == 0
    assert not (tmp_path / 'build').exists()
    assert len(uv_calls.cmds) == 4  # then set up from scratch as usual


def test_rmtree_retries_a_failed_removal_after_making_it_writable(tmp_path, monkeypatch):
    target = tmp_path / 'locked'
    target.write_bytes(b'x')
    target.chmod(stat.S_IREAD)
    attempts = []
    real_rmtree = shutil.rmtree

    def rmtree_failing_once(path, **kwargs):
        handler = kwargs.get('onexc') or kwargs.get('onerror')
        attempts.append(handler)
        handler(os.remove, str(target), PermissionError())  # what Windows reports for a read-only file
        real_rmtree(path)

    monkeypatch.setattr(xx_build.shutil, 'rmtree', rmtree_failing_once)
    xx_build._rmtree(tmp_path)
    assert attempts and not target.exists() and not tmp_path.exists()


# ------------------------------------------------------------------------------------- build modes

PYPROJECT = """
[project]
name = "x"

[tool.dev_10x.modes.dev-release.config-settings-package]
k = { "cmake.build-type" = "Release" }

[tool.uv]
required-version = ">=0.12.5"
no-build-isolation-package = ["k"]
default-groups = ["dev"]

[tool.uv.sources]
k = { path = "k", editable = true }
"""


@pytest.fixture
def repo(tmp_path) -> Path:
    (tmp_path / 'pyproject.toml').write_text(PYPROJECT, encoding='utf-8')
    return tmp_path


def test_render_copies_tool_uv_settings_and_merges_the_mode(repo):
    import tomllib

    text = xx_build.render('dev-release', repo)
    assert xx_build.HEADER_MODE.match(text).group(1) == 'dev-release'
    assert tomllib.loads(text) == {
        'required-version': '>=0.12.5',
        'no-build-isolation-package': ['k'],
        'config-settings-package': {'k': {'cmake.build-type': 'Release'}},
    }  # sources / default-groups stay in pyproject.toml: uv rejects them in uv.toml


def test_render_rejects_an_unknown_mode(repo):
    with pytest.raises(ValueError, match="unknown build mode 'bogus'"):
        xx_build.render('bogus', repo)


def test_mode_round_trip(repo):
    assert xx_build.active_mode(repo) == 'dev'
    xx_build.write_mode('dev-release', repo)
    assert xx_build.active_mode(repo) == 'dev-release'
    xx_build.write_mode('dev', repo)
    assert not (repo / 'uv.toml').exists() and xx_build.active_mode(repo) == 'dev'


def test_a_foreign_uv_toml_is_left_alone(repo):
    (repo / 'uv.toml').write_text('cache-dir = "/x"\n', encoding='utf-8')
    assert xx_build.active_mode(repo) is None
    with pytest.raises(ValueError, match='not written by xx-build'):
        xx_build.write_mode('dev', repo)
    assert (repo / 'uv.toml').exists()


def test_init_refuses_a_foreign_uv_toml_before_creating_a_venv(repo, uv_calls):
    """Without --mode, init must not keep a foreign uv.toml and print 'build mode None'."""
    text = 'cache-dir = "/x"\n'
    (repo / 'uv.toml').write_text(text, encoding='utf-8')
    with pytest.raises(ValueError, match='not written by xx-build'):
        xx_build.init(clean=False, sync_args=[], root=repo)
    for name in ('.venv', 'build'):
        (repo / name).mkdir()
    with pytest.raises(ValueError, match='not written by xx-build'):
        xx_build.init(clean=True, sync_args=[], root=repo)
    assert (repo / '.venv').is_dir() and (repo / 'build').is_dir()
    assert (repo / 'uv.toml').read_text(encoding='utf-8') == text
    assert uv_calls.cmds == []


def test_show_mode_flags_a_stale_uv_toml(repo, capsys):
    assert xx_build.show_mode(repo) == 0
    xx_build.write_mode('dev-release', repo)
    assert xx_build.show_mode(repo) == 0
    assert 'build mode: dev-release' in capsys.readouterr().out
    (repo / 'pyproject.toml').write_text(PYPROJECT.replace('["k"]', '["k", "j"]'), encoding='utf-8')
    assert xx_build.show_mode(repo) == 1
    assert 'run `./xx-build rebuild`' in capsys.readouterr().err


def test_set_mode_writes_uv_toml_then_syncs_in_order(repo, uv_calls):
    (repo / '.venv').mkdir()
    assert xx_build.set_mode('dev-release', ['--locked'], repo) == 0
    assert xx_build.active_mode(repo) == 'dev-release'
    assert uv_calls.cmds == xx_build.sync_commands(['--locked'])  # no `uv venv`; kernel before cxxfin


def test_set_mode_without_a_venv_only_writes_uv_toml(repo, uv_calls, capsys):
    assert xx_build.set_mode('dev-release', [], repo) == 0
    assert xx_build.active_mode(repo) == 'dev-release' and uv_calls.cmds == []
    assert './xx-build init' in capsys.readouterr().out


def test_init_mode_writes_uv_toml_before_building(repo, monkeypatch):
    modes = []

    def fake_run(cmd, cwd=None, env=None, check=False):
        modes.append(xx_build.active_mode(repo))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(xx_build.subprocess, 'run', fake_run)
    assert xx_build.init(clean=False, sync_args=[], root=repo, mode='dev-release') == 0
    assert modes == ['dev-release'] * 4


def test_init_clean_keeps_the_mode(repo, uv_calls):
    xx_build.write_mode('dev-release', repo)
    (repo / '.venv').mkdir()
    assert xx_build.init(clean=True, sync_args=[], root=repo) == 0
    assert xx_build.active_mode(repo) == 'dev-release'


def test_a_completed_switch_is_recorded(repo, uv_calls):
    (repo / '.venv').mkdir()
    assert xx_build.set_mode('dev-release', [], repo) == 0
    assert (repo / xx_build.SYNCED_MODE).read_text(encoding='utf-8').strip() == 'dev-release'
    assert xx_build.show_mode(repo) == 0


def test_an_interrupted_switch_is_reported(repo, monkeypatch, capsys):
    """Windows: a process holding a .pyd makes the sync fail mid-switch; uv.toml already names the new mode."""
    (repo / '.venv').mkdir()
    monkeypatch.setattr(xx_build.subprocess, 'run', lambda cmd, **kw: subprocess.CompletedProcess(cmd, 2))
    assert xx_build.set_mode('dev-release', [], repo) == 2
    assert 'run `./xx-build rebuild`' in capsys.readouterr().err
    assert xx_build.show_mode(repo) == 1
    assert 'not fully in build mode dev-release' in capsys.readouterr().err


def test_partial_sync_steps_leave_the_rest_of_the_venv_installed():
    """An exact partial sync would uninstall everything else first; only the final full sync is exact."""
    first, second, last = xx_build.sync_commands([])
    assert '--inexact' in first and '--inexact' in second and '--inexact' not in last
