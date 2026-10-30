"""Guards for `xx-constraints`: first-party exclusion, uv.lock -> constraints.txt export, consistency check."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from dev_10x import constraints as c


def _source_root() -> Path | None:
    """Repo root when this file lives in a py10x checkout; None for a wheel-only install.

    Pre-publish CI installs py10x-core from PyPI and runs with cwd under a temp RUN_DIR, so
    ``constraints.PROJECT_ROOT`` (``Path.cwd()``) has no pyproject — these live-tree tests skip.
    """
    root = Path(__file__).resolve().parents[2]
    return root if (root / 'pyproject.toml').is_file() else None


@pytest.fixture(autouse=True)
def _project_root_from_source(monkeypatch):
    root = _source_root()
    if root is None:
        pytest.skip('py10x source checkout (no pyproject next to installed tests)')
    monkeypatch.setattr(c, 'PROJECT_ROOT', root)


def test_downstreams_reads_configured_map():
    """Live `[tool.dev_10x.downstream]` paths resolve to each package's pyproject."""
    ds = c._downstreams()
    assert 'py10x-fin-base' in ds
    assert ds['py10x-fin-base'].name == 'pyproject.toml'


def test_first_party_includes_configured_downstreams(monkeypatch):
    monkeypatch.setattr(c, '_siblings', lambda: {'py10x-kernel': Path('k')})
    monkeypatch.setattr(c, '_downstreams', lambda: {'py10x-fin-base': Path('f')})
    monkeypatch.setattr(c, '_workspace_members', lambda: set())
    names = c._first_party()
    assert 'py10x-fin-base' in names
    assert 'py10x-kernel' in names
    assert 'py10x-core' in names


def test_workspace_members_include_nested_downstream_workspace():
    """fin-base's `[tool.uv.workspace] members = ["cxxfin"]` → no-emit `py10x-fin-base-cxx`."""
    assert 'py10x-fin-base-cxx' in c._workspace_members()
    assert 'py10x-fin-base-cxx' in c._first_party()


def test_no_emit_is_first_party_only():
    """Root + registered packages + nested workspace members — no separate py10x-* dep scan."""
    names = c._first_party()
    assert 'py10x-core' in names
    assert 'py10x-fin-base' in names
    assert 'py10x-fin-base-cxx' in names


def test_export_excludes_every_first_party_package(monkeypatch):
    """`uv export` gets `--no-emit-package` for each first-party name, plus all extras and groups."""
    monkeypatch.setenv('UV', '/opt/uv')
    cmd = c._export_cmd()
    assert cmd[:2] == ['/opt/uv', 'export']
    assert {'--frozen', '--all-extras', '--all-groups', '--no-hashes', '--no-header'} <= set(cmd)
    emitted_off = {cmd[i + 1] for i, a in enumerate(cmd) if a == '--no-emit-package'}
    assert emitted_off == c._first_party()
    assert {'py10x-core', 'py10x-kernel', 'py10x-infra', 'py10x-fin-base', 'py10x-fin-base-cxx'} <= emitted_off


def test_uv_falls_back_to_path_uv(monkeypatch):
    monkeypatch.delenv('UV', raising=False)
    assert c._uv() == 'uv'


def test_check_export_detects_drift(monkeypatch, tmp_path, capsys):
    target = tmp_path / 'constraints.txt'
    monkeypatch.setattr(c, 'CONSTRAINTS', target)
    monkeypatch.setattr(c, '_export', lambda: c.HEADER + 'six==1.0\n')
    target.write_text(c.HEADER + 'six==1.0\n', encoding='utf-8')
    assert c.check_export() == 0
    target.write_text(c.HEADER + 'six==2.0\n', encoding='utf-8')
    assert c.check_export() == 1
    assert 'does not match uv.lock' in capsys.readouterr().out


def test_compile_writes_export_and_lock_change_summary(monkeypatch, tmp_path):
    target, summary = tmp_path / 'constraints.txt', tmp_path / 'changes.txt'
    monkeypatch.setattr(c, 'CONSTRAINTS', target)
    monkeypatch.setattr(c, '_export', lambda: c.HEADER + 'six==2.0\n')
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        stderr = 'Resolved 3 packages in 1ms\nUpdated six v1.0 -> v2.0\nAdded tomli v2.0.1\n'
        return subprocess.CompletedProcess(cmd, 0, stdout='', stderr=stderr)

    monkeypatch.setattr(c.subprocess, 'run', fake_run)
    assert c.compile_(upgrade=True, summary_file=summary) == 0
    assert calls[0][-2:] == ['lock', '--upgrade']
    assert target.read_text(encoding='utf-8') == c.HEADER + 'six==2.0\n'
    assert summary.read_text(encoding='utf-8') == 'Updated six v1.0 -> v2.0\nAdded tomli v2.0.1\n'


def test_compile_summary_file_without_path_exits_with_usage(monkeypatch, capsys):
    """A bare --summary-file must exit with the usage string, not IndexError."""
    monkeypatch.setattr(sys, 'argv', ['xx-constraints', 'compile', '--summary-file'])
    with pytest.raises(SystemExit) as caught:
        c.main()
    assert caught.value.code not in (0, None)
    captured = capsys.readouterr()
    assert '--summary-file PATH' in captured.out + captured.err


def test_compile_stops_on_lock_failure(monkeypatch, tmp_path):
    target = tmp_path / 'constraints.txt'
    monkeypatch.setattr(c, 'CONSTRAINTS', target)
    monkeypatch.setattr(c.subprocess, 'run', lambda cmd, **kw: subprocess.CompletedProcess(cmd, 2, stdout='', stderr='boom\n'))
    assert c.compile_() == 2
    assert not target.exists()


def test_committed_constraints_match_committed_lock():
    """The repo's constraints.txt is exactly `uv export` of its uv.lock (needs uv on PATH)."""
    import shutil

    if shutil.which('uv') is None or not (c.PROJECT_ROOT / 'uv.lock').is_file():
        pytest.skip('uv or uv.lock not available')
    assert c.check_export() == 0
