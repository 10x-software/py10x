"""Collection gates for in-repo downstream trees (core isolation vs --with-downstream)."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev_10x import pytest_plugin as pp


@pytest.fixture(autouse=True)
def _clear_collect_caches():
    pp._owned_top_levels.clear()
    pp._hatch_wheel_packages.clear()
    pp._downstream_tops.clear()
    yield
    pp._owned_top_levels.clear()
    pp._hatch_wheel_packages.clear()
    pp._downstream_tops.clear()


def test_hatch_wheel_packages_exclude_xx_fin():
    tops = pp._hatch_wheel_packages()
    assert 'core_10x' in tops
    assert 'xx_fin' not in tops


def test_downstream_tops_maps_xx_fin():
    if not (pp.PY10X_ROOT / 'xx_fin' / 'pyproject.toml').is_file():
        pytest.skip('xx_fin not in tree')
    assert pp._downstream_tops().get('xx_fin') == 'py10x-fin-base'


def test_ignore_xx_fin_when_fin_base_not_installed(monkeypatch):
    if not (pp.PY10X_ROOT / 'xx_fin' / 'pyproject.toml').is_file():
        pytest.skip('xx_fin not in tree')

    monkeypatch.setattr(pp, '_dist_installed', lambda _name: False)
    # Force hatch fallback path (editable RECORD often yields empty tops).
    monkeypatch.setattr(pp, '_owned_top_levels', lambda: pp._hatch_wheel_packages())

    path = pp.PY10X_ROOT / 'xx_fin' / 'xxfin' / 'unit_tests' / 'test_ccy.py'
    assert pp.pytest_ignore_collect(path, config=None) is True


def test_allow_xx_fin_when_fin_base_installed(monkeypatch):
    if not (pp.PY10X_ROOT / 'xx_fin' / 'pyproject.toml').is_file():
        pytest.skip('xx_fin not in tree')

    monkeypatch.setattr(pp, '_dist_installed', lambda name: name == 'py10x-fin-base')
    monkeypatch.setattr(pp, '_owned_top_levels', lambda: pp._hatch_wheel_packages())

    path = pp.PY10X_ROOT / 'xx_fin' / 'xxfin' / 'unit_tests' / 'test_ccy.py'
    assert pp.pytest_ignore_collect(path, config=None) is False


def test_still_collects_core_unit_tests(monkeypatch):
    monkeypatch.setattr(pp, '_owned_top_levels', lambda: pp._hatch_wheel_packages())
    path = pp.PY10X_ROOT / 'core_10x' / 'unit_tests' / 'test_bundle.py'
    if not path.is_file():
        path = next((pp.PY10X_ROOT / 'core_10x' / 'unit_tests').glob('test_*.py'))
    assert pp.pytest_ignore_collect(path, config=None) is False
