"""Regression tests for module/session TsStore pinning vs test_isolation clears.

Lifecycle:

  pin_current_ts_stores()   # just before yield (main + vault + NamedTsStore targets)
  ... tests; isolation does reset + restore_pinned (top frame only) ...
  unpin_ts_stores()         # pop frame; same reset + restore
"""

from __future__ import annotations

import pytest
from core_10x.environment_variables import EnvVars
from core_10x.py_class import PyClass
from core_10x.testlib.ts_store_isolation import (
    _pin_stack,
    clear_traitable_store_state,
    pin_current_ts_stores,
    pinned_ts_stores,
    reset_traitable_process_state,
    restore_pinned_ts_stores,
    unpin_ts_stores,
)
from core_10x.traitable import NamedTsStore, T, Traitable, TsClassAssociation
from core_10x.ts_store import TsStore
from core_10x.xnone import XNone
from infra_10x.duckdb_store import DuckDbStore


class _SeedMarker(Traitable):
    """Module-level storable used to prove the same DuckDB survived isolation."""

    name: str = T(T.ID)


def _make_main(uri: str):
    EnvVars.main_ts_store_uri = uri
    Traitable.main_store.clear()
    Traitable.store_per_class.__func__.cache.clear()
    store = Traitable.main_store()
    assert isinstance(store, DuckDbStore)
    return store


def _assert_store_clean():
    from core_10x.testlib.ts_store_isolation import _ENV_CLASSPROPERTIES

    assert Traitable.main_store.value[0] is XNone
    assert Traitable.vault_store.value[0] is XNone
    assert not TsStore.s_instances
    for name, desc in _ENV_CLASSPROPERTIES.items():
        assert EnvVars.__dict__.get(name) is desc, name
    assert not EnvVars.main_ts_store_uri
    assert not EnvVars.main_vault_uri
    assert not _pin_stack


def _simulate_test_isolation():
    """Mirror dev_10x.pytest_plugin.test_isolation store reset (no BTP rotate)."""
    reset_traitable_process_state()
    restore_pinned_ts_stores()


# ---------------------------------------------------------------------------
# Direct API
# ---------------------------------------------------------------------------


def test_clear_traitable_store_state_wipes_bindings():
    store = _make_main('duckdb://localhost/iso_clear')
    assert Traitable.main_store.value[0] is store
    assert store in TsStore.s_instances.values()
    EnvVars.use_ts_store_transactions = True  # also pollutes a non-URI classproperty

    clear_traitable_store_state()

    _assert_store_clean()
    assert EnvVars.use_ts_store_transactions is False


def test_pin_survives_isolation_clear_and_restore():
    store = _make_main('duckdb://localhost/iso_pin')
    pin_current_ts_stores()
    try:
        _simulate_test_isolation()
        assert Traitable.main_store.value[0] is store
        assert EnvVars.main_ts_store_uri == 'duckdb://localhost/iso_pin'
        assert store in TsStore.s_instances.values()
        assert Traitable.main_store() is store
    finally:
        unpin_ts_stores()
    _assert_store_clean()


def test_unpin_leaves_process_store_clean():
    store = _make_main('duckdb://localhost/iso_unpin')
    pin_current_ts_stores()
    assert Traitable.main_store.value[0] is store

    unpin_ts_stores()

    _assert_store_clean()
    with pytest.raises(OSError, match='No Traitable Store is specified'):
        Traitable.main_store()


def test_nested_pins_inner_unpin_restores_outer():
    """Session-like outer pin + nested module pin (only main/associations of each)."""
    outer = _make_main('duckdb://localhost/iso_outer')
    pin_current_ts_stores()
    try:
        EnvVars.main_ts_store_uri = 'duckdb://localhost/iso_inner'
        Traitable.main_store.clear()
        TsStore.s_instances.clear()
        inner = Traitable.main_store()
        pin_current_ts_stores()
        try:
            assert Traitable.main_store.value[0] is inner
            _simulate_test_isolation()
            assert Traitable.main_store.value[0] is inner
            assert EnvVars.main_ts_store_uri == 'duckdb://localhost/iso_inner'
            # Outer not part of inner pin (no NamedTsStore link)
            assert outer not in TsStore.s_instances.values()
        finally:
            unpin_ts_stores()

        assert Traitable.main_store.value[0] is outer
        assert EnvVars.main_ts_store_uri == 'duckdb://localhost/iso_outer'
        assert outer in TsStore.s_instances.values()
        assert inner not in TsStore.s_instances.values()

        _simulate_test_isolation()
        assert Traitable.main_store.value[0] is outer
    finally:
        unpin_ts_stores()
    _assert_store_clean()


def test_nested_pin_hides_outer_class_associations():
    """Outer session associations must not apply under a nested pin of a clean main."""

    class _AssocProbe(Traitable):
        name: str = T(T.ID)

    _AssocProbe.__module__ = 'core_10x.unit_tests.test_ts_store_isolation'

    _make_main('duckdb://localhost/iso_assoc_outer')
    NamedTsStore(logical_name='probe_store', uri='duckdb://localhost/iso_probe', _replace=True).save().throw()
    TsClassAssociation(
        py_canonical_name=PyClass.name(_AssocProbe),
        ts_logical_name='probe_store',
        _replace=True,
    ).save().throw()
    assert TsClassAssociation.ts_uri(_AssocProbe) == 'duckdb://localhost/iso_probe'
    pin_current_ts_stores()
    try:
        probe = Traitable.store_from_uri('duckdb://localhost/iso_probe')
        assert probe in _pin_stack[-1][0].values()

        EnvVars.main_ts_store_uri = 'duckdb://localhost/iso_assoc_inner'
        Traitable.main_store.clear()
        TsStore.s_instances.clear()
        Traitable.main_store()
        pin_current_ts_stores()
        try:
            _simulate_test_isolation()
            assert TsClassAssociation.ts_uri(_AssocProbe) == ''
        finally:
            unpin_ts_stores()
        assert TsClassAssociation.ts_uri(_AssocProbe) == 'duckdb://localhost/iso_probe'
    finally:
        unpin_ts_stores()
    _assert_store_clean()


def test_pinned_ts_stores_context_manager():
    store = _make_main('duckdb://localhost/iso_cm')
    with pinned_ts_stores():
        _simulate_test_isolation()
        assert Traitable.main_store.value[0] is store
    _assert_store_clean()


def test_named_ts_store_associations_are_pinned_and_opened():
    """NamedTsStore rows on main are opened and held across isolation."""
    main = _make_main('duckdb://localhost/iso_main_named')
    NamedTsStore(
        logical_name='secondary',
        uri='duckdb://localhost/iso_secondary',
        _replace=True,
    ).save().throw()
    # Not yet open
    assert all(getattr(s, 'dbname', None) != 'iso_secondary' for s in TsStore.s_instances.values())

    pin_current_ts_stores()
    try:
        secondary = Traitable.store_from_uri('duckdb://localhost/iso_secondary')
        assert secondary in TsStore.s_instances.values()
        _simulate_test_isolation()
        assert Traitable.main_store.value[0] is main
        assert secondary in TsStore.s_instances.values()
        assert main in TsStore.s_instances.values()
    finally:
        unpin_ts_stores()
    _assert_store_clean()


def test_orphan_open_store_not_pinned_without_named_row():
    """A random DuckDbStore.instance is not pinned unless NamedTsStore names it."""
    main = _make_main('duckdb://localhost/iso_main_orphan')
    orphan = DuckDbStore.instance(hostname='localhost', dbname='iso_orphan', protocol='duckdb')
    pin_current_ts_stores()
    try:
        _simulate_test_isolation()
        assert Traitable.main_store.value[0] is main
        assert orphan not in TsStore.s_instances.values()
    finally:
        unpin_ts_stores()
    _assert_store_clean()


def test_vault_uri_is_pinned_and_store_opened_when_configured():
    EnvVars.main_ts_store_uri = 'duckdb://localhost/iso_main_v'
    EnvVars.main_vault_uri = 'duckdb://localhost/iso_vault_v'
    Traitable.main_store.clear()
    Traitable.vault_store.clear()
    main = Traitable.main_store()
    pin_current_ts_stores()
    try:
        vault = Traitable.vault_store.value[0]
        assert vault is not XNone
        assert vault is not main
        _simulate_test_isolation()
        assert EnvVars.main_vault_uri == 'duckdb://localhost/iso_vault_v'
        assert Traitable.vault_store.value[0] is vault
    finally:
        unpin_ts_stores()
    _assert_store_clean()


# ---------------------------------------------------------------------------
# Real pytest module scope
# ---------------------------------------------------------------------------


@pytest.fixture(scope='module')
def module_pinned_main():
    store = _make_main('duckdb://localhost/iso_module')
    _SeedMarker(name='seed').save(save_references=True).throw()
    pin_current_ts_stores()
    try:
        yield store
    finally:
        unpin_ts_stores()


def test_module_pin_visible_on_first_test(module_pinned_main):
    assert Traitable.main_store.value[0] is module_pinned_main
    assert EnvVars.main_ts_store_uri == 'duckdb://localhost/iso_module'


def test_module_pin_survives_prior_test_isolation(module_pinned_main):
    assert Traitable.main_store.value[0] is module_pinned_main
    loaded = _SeedMarker.load_many()
    assert any(m.name == 'seed' for m in loaded)


def test_module_pin_after_explicit_isolation_sim(module_pinned_main):
    _simulate_test_isolation()
    assert Traitable.main_store.value[0] is module_pinned_main
    assert module_pinned_main in TsStore.s_instances.values()
    assert any(m.name == 'seed' for m in _SeedMarker.load_many())


def test_reset_skips_dead_weakref_proxies():
    """Leftover scan must not dereference weakref proxies (isinstance would raise)."""
    import gc
    import weakref

    from core_10x.trait_definition import RT

    class _Leaf(Traitable):
        name: str = RT(T.ID)

    obj = _Leaf(name='weak-proxy-probe')
    proxy = weakref.proxy(obj)
    del obj
    gc.collect()
    with pytest.raises(ReferenceError):
        isinstance(proxy, Traitable)
    assert not issubclass(type(proxy), Traitable)

    reset_traitable_process_state()
