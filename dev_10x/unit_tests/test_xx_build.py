"""`xx-build init`: refusal on an existing environment, `--clean`, command order, stdlib-only imports."""

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


def test_imports_only_the_standard_library():
    """It runs before the venv exists (`uv run --no-project --isolated -m dev_10x.xx_build`)."""
    tree = ast.parse(Path(xx_build.__file__).read_text(encoding='utf-8'))
    modules = {alias.name.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    modules |= {node.module.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert modules - {'__future__'} <= set(sys.stdlib_module_names)


def test_init_orders_toolchain_then_kernel_then_everything(tmp_path, uv_calls):
    assert xx_build.init(clean=False, sync_args=['--locked'], root=tmp_path) == 0
    assert uv_calls.cmds == [
        ['uv', 'venv'],
        ['uv', 'sync', '--frozen', '--only-group', 'build'],
        [
            'uv', 'sync', '--no-default-groups', '--group', 'build',
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


def test_init_stops_at_the_first_failing_step(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, cwd=None, env=None, check=False):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 3 if len(calls) == 2 else 0)

    monkeypatch.setattr(xx_build.subprocess, 'run', fake_run)
    assert xx_build.init(clean=False, sync_args=[], root=tmp_path) == 3
    assert len(calls) == 2


def test_main_parses_clean_and_forwards_the_rest(monkeypatch):
    seen = {}
    monkeypatch.setattr(xx_build, 'init', lambda clean, sync_args: seen.update(clean=clean, args=sync_args) or 0)
    assert xx_build.main(['init', '--clean', '--locked', '--config-file', 'uv.ci-release.toml']) == 0
    assert seen == {'clean': True, 'args': ['--locked', '--config-file', 'uv.ci-release.toml']}
    assert xx_build.main(['bogus']) == 2


def test_wrapper_runs_isolated_without_the_project():
    root = Path(__file__).resolve().parents[2]
    wrapper = root / 'xx-build'
    if not wrapper.is_file():
        pytest.skip('repo-root wrapper not present (installed-package test run)')
    text = wrapper.read_text(encoding='utf-8')
    assert '\r' not in text
    assert 'uv run --no-project --isolated -m dev_10x.xx_build "$@"' in text


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
