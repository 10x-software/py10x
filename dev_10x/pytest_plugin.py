from __future__ import annotations

import importlib.metadata as md
import os
from pathlib import Path

import core_10x
import pytest
from core_10x.global_cache import cache
from py10x_kernel import BTraitableProcessor

PY10X_ROOT = Path(core_10x.__file__).resolve().parent.parent


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
        if top and '.' not in top:
            tops.add(top)

    return tops or None


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
    """Only constrain collection for py10x package paths."""
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
    if tops and parts[0] not in tops:
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

        # On failed/skipped call phases, still clear state but skip leftover assert:
        # locals / assertion frames often still hold Traitables and only add noise.
        rep_call = getattr(request.node, 'rep_call', None)
        reset_traitable_process_state(assert_clean=rep_call is None or rep_call.passed)
        restore_pinned_ts_stores()
