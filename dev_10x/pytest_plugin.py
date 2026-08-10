from __future__ import annotations

import importlib.metadata as md
import os
from pathlib import Path

import core_10x
import pytest
import tomlkit
from core_10x.global_cache import cache

# Cross-package / pre-publish fixtures must be registered here (pytest11 entry point),
# not in repo-root conftest.py — CI collects from site-packages and never loads that file.
from core_10x.testlib.test_databases import live_store
from py10x_kernel import BTraitableProcessor

PY10X_ROOT = Path(core_10x.__file__).resolve().parent.parent


@cache
def _hatch_wheel_packages() -> set[str]:
    """Top-level dirs shipped in the py10x-core wheel (from hatch config)."""
    try:
        doc = tomlkit.parse((PY10X_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
        pkgs = doc.get('tool', {}).get('hatch', {}).get('build', {}).get('targets', {}).get('wheel', {}).get('packages', [])
        return {str(p) for p in pkgs}
    except Exception:  # noqa: BLE001 - best-effort fallback
        return set()


@cache
def _downstream_tops() -> dict[str, str]:
    """Map in-repo top-level dir → dist name for `[tool.dev_10x.downstream]`."""
    try:
        doc = tomlkit.parse((PY10X_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
        ds = doc.get('tool', {}).get('dev_10x', {}).get('downstream', {}) or {}
        out: dict[str, str] = {}
        for name, spec in ds.items():
            path = str(spec.get('path', '') if hasattr(spec, 'get') else '')
            top = Path(path).as_posix().lstrip('./').split('/', 1)[0]
            if top:
                out[top] = str(name)
        return out
    except Exception:  # noqa: BLE001 - best-effort fallback
        return {}


@cache
def _owned_top_levels() -> set[str] | None:
    try:
        files = md.distribution('py10x-core').files or []
    except md.PackageNotFoundError:
        return None

    tops: set[str] = set()
    for f in files:
        p = Path(f)
        if not p.parts:
            continue
        top = p.parts[0]
        # Editable RECORDs are mostly `../…` scripts and `*.pth` / dist-info — skip those.
        if not top or top in {'.', '..'} or '.' in top:
            continue
        tops.add(top)

    # Editable installs often yield no usable tops; fall back to declared wheel packages.
    return tops or _hatch_wheel_packages() or None


def _dist_installed(name: str) -> bool:
    try:
        md.distribution(name)
        return True
    except md.PackageNotFoundError:
        return False


def _tops_from_dist(name: str) -> set[str]:
    try:
        files = md.distribution(name).files or []
    except md.PackageNotFoundError:
        return set()
    tops: set[str] = set()
    for f in files:
        p = Path(f)
        if not p.parts:
            continue
        top = p.parts[0]
        if not top or top in {'.', '..'} or '.' in top:
            continue
        tops.add(top)
    return tops


@cache
def _installed_py10x_dist_names() -> frozenset[str]:
    """All installed distributions whose name starts with ``py10x-``."""
    names: set[str] = set()
    for dist in md.distributions():
        name = getattr(dist, 'name', None) or dist.metadata.get('Name') or ''
        if str(name).lower().startswith('py10x-'):
            names.add(str(name))
    return frozenset(names)


@cache
def _downstream_allowed_tops() -> set[str]:
    """Tops collectable from installed first-party / downstream packages.

    Includes in-repo path tops (``xx_fin``) from ``[tool.dev_10x.downstream]`` when
    that dist is installed, plus import tops from every installed ``py10x-*``
    distribution's RECORD (e.g. ``xxfin`` under site-packages).
    """
    allowed: set[str] = set()
    for top, dist_name in _downstream_tops().items():
        if _dist_installed(dist_name):
            allowed.add(top)
    for dist_name in _installed_py10x_dist_names():
        allowed |= _tops_from_dist(dist_name)
    return allowed


def pytest_configure(config):

    if 'USER' not in os.environ:
        import getpass

        os.environ['USER'] = getpass.getuser()

    try:
        config.pluginmanager.import_plugin('alt_pytest_asyncio.enable')
    except ImportError:
        return

    try:
        if not config.getini('default_async_timeout'):
            config._inicache['default_async_timeout'] = 30
    except (ValueError, KeyError):
        pass


def pytest_ignore_collect(collection_path, config):
    """Only constrain collection for py10x package paths.

    Core isolation (default CI): collect only wheel-owned tops. Other trees under the
    py10x root / site-packages (e.g. ``xx_fin/`` source or ``xxfin/`` installed) are
    ignored unless owned by an installed ``py10x-*`` distribution.
    """
    p = Path(collection_path).resolve()
    if not p.is_relative_to(PY10X_ROOT):
        # Returning None means "no opinion" so user package collection is unaffected.
        return None

    parts = p.relative_to(PY10X_ROOT).parts
    if not parts:
        return False

    if any('.venv' in part for part in parts):
        return True

    tops = _owned_top_levels()
    if tops and parts[0] not in tops and parts[0] not in _downstream_allowed_tops():
        return True

    if p.is_dir():
        return False

    # Do not ignore tests located in a unit_tests parent directory.
    return not (len(parts) > 1 and parts[-2] == 'unit_tests')


BTP = BTraitableProcessor.current()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Stash per-phase reports on the item so fixtures can see call outcome."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f'rep_{rep.when}', rep)


@pytest.fixture(autouse=True)
def test_isolation(request):
    global BTP
    assert BTP is BTraitableProcessor.current()

    # Snapshot test instance keys *before* setUp so we can drop attrs stored on self
    # during tearDown
    inst = getattr(request, 'instance', None)
    keys_before = set(vars(inst)) if inst is not None else None

    try:
        yield
    finally:
        assert BTP is BTraitableProcessor.current()
        BTP.end_using()
        BTP = BTraitableProcessor.current()

        from core_10x.testlib.ts_store_isolation import (
            drop_new_instance_attrs,
            reset_traitable_process_state,
            restore_pinned_ts_stores,
        )

        if keys_before is not None:
            drop_new_instance_attrs(inst, keys_before)

        # Only assert "no leftover Traitables" when the test *body* ran and passed.
        # On setup ERROR, ``rep_call`` is missing (call never ran) — the old
        # ``rep_call is None or …`` treated that as assert_clean and piled a
        # leftover AssertionError on top of the real failure. Failed/skipped
        # calls also skip the assert: frames often still hold Traitables.
        rep_call = getattr(request.node, 'rep_call', None)
        reset_traitable_process_state(assert_clean=rep_call is not None and rep_call.passed)
        restore_pinned_ts_stores()
