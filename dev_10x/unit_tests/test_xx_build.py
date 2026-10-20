"""`xx-build init`: refusal on an existing environment, `--clean`, command order, stdlib-only imports."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from dev_10x import xx_build


@pytest.fixture
def captured_runs(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, cwd=None, check=False):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(xx_build.subprocess, 'run', fake_run)
    monkeypatch.setenv('UV', '/opt/uv')
    return calls


def test_imports_only_the_standard_library():
    """It runs before the venv exists (`uv run --no-project --isolated -m dev_10x.xx_build`)."""
    tree = ast.parse(Path(xx_build.__file__).read_text(encoding='utf-8'))
    modules = {alias.name.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    modules |= {node.module.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert modules - {'__future__'} <= set(sys.stdlib_module_names)


def test_init_orders_toolchain_then_kernel_then_everything(tmp_path, captured_runs):
    assert xx_build.init(clean=False, sync_args=['--locked'], root=tmp_path) == 0
    assert captured_runs == [
        ['/opt/uv', 'venv'],
        ['/opt/uv', 'sync', '--frozen', '--only-group', 'build'],
        [
            '/opt/uv', 'sync', '--no-default-groups', '--group', 'build',
            '--reinstall-package', 'py10x-kernel', '--reinstall-package', 'py10x-infra', '--locked',
        ],
        ['/opt/uv', 'sync', '--reinstall-package', 'py10x-fin-base-cxx', '--locked'],
    ]  # fmt: skip


@pytest.mark.parametrize('existing', ['.venv', 'build'])
def test_init_refuses_an_existing_environment(tmp_path, captured_runs, capsys, existing):
    (tmp_path / existing).mkdir()
    assert xx_build.init(clean=False, sync_args=[], root=tmp_path) == 1
    assert captured_runs == []
    assert '--clean' in capsys.readouterr().err


def test_init_clean_deletes_venv_and_build_then_runs(tmp_path, captured_runs):
    for name in ('.venv', 'build'):
        (tmp_path / name / 'sub').mkdir(parents=True)
    assert xx_build.init(clean=True, sync_args=[], root=tmp_path) == 0
    assert not (tmp_path / '.venv').exists()
    assert not (tmp_path / 'build').exists()
    assert len(captured_runs) == 4


def test_init_stops_at_the_first_failing_step(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, cwd=None, check=False):
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
