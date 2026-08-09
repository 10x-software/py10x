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
    pp._installed_py10x_dist_names.clear()
    pp._downstream_allowed_tops.clear()
    yield
    pp._owned_top_levels.clear()
    pp._hatch_wheel_packages.clear()
    pp._downstream_tops.clear()
    pp._installed_py10x_dist_names.clear()
    pp._downstream_allowed_tops.clear()


def test_hatch_wheel_packages_exclude_xx_fin():
    tops = pp._hatch_wheel_packages()
    # Wheel-only installs (kernel pre-publish): PY10X_ROOT is site-packages — no hatch config.
    if not tops:
        pytest.skip('source pyproject.toml not available next to installed core_10x')
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


def test_allow_installed_xxfin_when_py10x_dist_owns_it(monkeypatch, tmp_path):
    """Domain / wheel layout: PY10X_ROOT is site-packages; import top is xxfin not xx_fin."""
    site = tmp_path / 'site-packages'
    (site / 'xxfin' / 'unit_tests').mkdir(parents=True)
    test_py = site / 'xxfin' / 'unit_tests' / 'test_ccy.py'
    test_py.write_text('# stub\n', encoding='utf-8')

    monkeypatch.setattr(pp, 'PY10X_ROOT', site)
    monkeypatch.setattr(pp, '_owned_top_levels', lambda: {'core_10x', 'dev_10x'})
    monkeypatch.setattr(pp, '_downstream_tops', lambda: {})  # no source pyproject
    monkeypatch.setattr(pp, '_installed_py10x_dist_names', lambda: frozenset({'py10x-fin-base'}))
    monkeypatch.setattr(pp, '_tops_from_dist', lambda name: {'xxfin'} if name == 'py10x-fin-base' else set())

    assert pp.pytest_ignore_collect(test_py, config=None) is False
    assert pp.pytest_ignore_collect(site / 'xxfin' / 'unit_tests', config=None) is False


def test_ignore_installed_xxfin_when_no_py10x_dist_owns_it(monkeypatch, tmp_path):
    site = tmp_path / 'site-packages'
    test_py = site / 'xxfin' / 'unit_tests' / 'test_ccy.py'
    test_py.parent.mkdir(parents=True)
    test_py.write_text('# stub\n', encoding='utf-8')

    monkeypatch.setattr(pp, 'PY10X_ROOT', site)
    monkeypatch.setattr(pp, '_owned_top_levels', lambda: {'core_10x'})
    monkeypatch.setattr(pp, '_downstream_tops', lambda: {})
    monkeypatch.setattr(pp, '_installed_py10x_dist_names', lambda: frozenset())
    monkeypatch.setattr(pp, '_dist_installed', lambda _name: False)

    assert pp.pytest_ignore_collect(test_py, config=None) is True


def test_still_collects_core_unit_tests(monkeypatch):
    monkeypatch.setattr(pp, '_owned_top_levels', lambda: pp._hatch_wheel_packages())
    path = pp.PY10X_ROOT / 'core_10x' / 'unit_tests' / 'test_bundle.py'
    if not path.is_file():
        path = next((pp.PY10X_ROOT / 'core_10x' / 'unit_tests').glob('test_*.py'))
    assert pp.pytest_ignore_collect(path, config=None) is False
