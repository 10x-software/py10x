"""Guards for `xx-constraints` first-party / compile-input inclusion of downstreams."""

from __future__ import annotations

from pathlib import Path

from dev_10x import constraints as c


def test_downstreams_empty_when_unconfigured():
    """Live `[tool.dev_10x.downstream]` defaults to {} until a package is registered (PR1)."""
    assert c._downstreams() == {}


def test_first_party_includes_configured_downstreams(monkeypatch):
    monkeypatch.setattr(c, '_siblings', lambda: {'py10x-kernel': Path('k')})
    monkeypatch.setattr(c, '_downstreams', lambda: {'py10x-fin-base': Path('f')})
    monkeypatch.setattr(c, '_workspace_members', lambda: set())
    names = c._first_party()
    assert 'py10x-fin-base' in names
    assert 'py10x-kernel' in names
    assert 'py10x-core' in names


def test_compile_inputs_merge_siblings_and_downstreams(monkeypatch, tmp_path):
    sib = tmp_path / 'sib' / 'pyproject.toml'
    ds = tmp_path / 'xx_fin' / 'pyproject.toml'
    for p in (sib, ds):
        p.parent.mkdir(parents=True)
        p.write_text('[project]\nname="x"\n', encoding='utf-8')
    monkeypatch.setattr(c, '_siblings', lambda: {'py10x-kernel': sib})
    monkeypatch.setattr(c, '_downstreams', lambda: {'py10x-fin-base': ds})
    compile_inputs = {**c._siblings(), **c._downstreams()}
    assert set(compile_inputs) == {'py10x-kernel', 'py10x-fin-base'}
