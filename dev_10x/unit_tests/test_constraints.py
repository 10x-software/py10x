"""Guards for `xx-constraints` first-party / compile-input inclusion of downstreams."""

from __future__ import annotations

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


def test_compile_inputs_default_siblings_only(monkeypatch, tmp_path):
    sib = tmp_path / 'sib' / 'pyproject.toml'
    ds = tmp_path / 'xx_fin' / 'pyproject.toml'
    for p in (sib, ds):
        p.parent.mkdir(parents=True)
        p.write_text('[project]\nname="x"\n', encoding='utf-8')
    monkeypatch.setattr(c, '_siblings', lambda: {'py10x-kernel': sib})
    monkeypatch.setattr(c, '_downstreams', lambda: {'py10x-fin-base': ds})
    assert set(c._compile_inputs()) == {'py10x-kernel'}


def test_compile_inputs_with_downstream_opt_in(monkeypatch, tmp_path):
    sib = tmp_path / 'sib' / 'pyproject.toml'
    ds = tmp_path / 'xx_fin' / 'pyproject.toml'
    for p in (sib, ds):
        p.parent.mkdir(parents=True)
        p.write_text('[project]\nname="x"\n', encoding='utf-8')
    monkeypatch.setattr(c, '_siblings', lambda: {'py10x-kernel': sib})
    monkeypatch.setattr(c, '_downstreams', lambda: {'py10x-fin-base': ds})
    assert set(c._compile_inputs(with_downstream=True)) == {'py10x-kernel', 'py10x-fin-base'}
    assert set(c._compile_inputs(with_downstream=True, downstream_filter={'py10x-fin-base'})) == {
        'py10x-kernel',
        'py10x-fin-base',
    }


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
