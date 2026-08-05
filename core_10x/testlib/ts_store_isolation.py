"""Pin TsStores so they survive py10x_core's per-test ``test_isolation`` clears.

Module- and session-scoped fixtures that build a Traitable store should pin
**just before yield** (after seed data / associations are written), then unpin
on teardown::

    from core_10x.testlib.ts_store_isolation import pin_current_ts_stores, unpin_ts_stores

    @pytest.fixture(scope='session', autouse=True)
    def test_xxfin_main_store():
        ...  # create stores, seed data, NamedTsStore + TsClassAssociation rows
        pin_current_ts_stores()  # main + vault + stores named from main
        try:
            yield store
        finally:
            unpin_ts_stores()

What is pinned
--------------
Always (when configured / present):

1. **main** store (``EnvVars.main_ts_store_uri`` / ``Traitable.main_store``)
2. **vault** store (``EnvVars.main_vault_uri`` / ``Traitable.vault_store``)
3. Every **NamedTsStore** row found on the main store, opened via its ``uri``
   (e.g. ``mkt_data``, ``trades_and_positions``)

That is the full durable surface for a fixture: main config, vault, and
association-backed secondary stores. Nothing else from ``s_instances`` is
captured, so a nested pin under a still-active outer session pin does not
inherit the outer's associations.

Restore always re-publishes the **top** pin frame only.

``dev_10x.pytest_plugin.test_isolation`` and :func:`unpin_ts_stores` share
:func:`reset_traitable_process_state` + :func:`restore_pinned_ts_stores`.
"""

from __future__ import annotations

import gc
from contextlib import contextmanager
from typing import TYPE_CHECKING

from py10x_kernel import XCache

from core_10x.environment_variables import EnvVars, classproperty
from core_10x.global_cache import _clear_all_caches
from core_10x.py_class import PyClass
from core_10x.scenario import Scenario
from core_10x.traitable import NamedTsStore, Traitable, TsClassAssociation
from core_10x.ts_store import TsStore

if TYPE_CHECKING:
    from collections.abc import Iterator

# Each pin frame: (s_instances subset, main_or_None, vault_or_None)
# main/vault entries are (store, uri).
_pin_stack: list[tuple[dict, tuple | None, tuple | None]] = []

# Original EnvVars classproperties at import (before tests assign str over them).
_ENV_CLASSPROPERTIES: dict[str, classproperty] = {name: value for name, value in EnvVars.__dict__.items() if isinstance(value, classproperty)}


def clear_traitable_store_state() -> None:
    """Drop Traitable store bindings (URIs, main/vault caches, store_per_class, s_instances)."""
    for name, desc in _ENV_CLASSPROPERTIES.items():
        setattr(EnvVars, name, desc)
        desc.fget.clear()

    Traitable.main_store.clear()
    Traitable.vault_store.clear()
    Traitable.store_per_class.__func__.cache.clear()
    TsClassAssociation.store_per_class.__func__.cache.clear()

    TsStore.s_instances.clear()


def drop_new_instance_attrs(inst: object, keys_before: set[str]) -> None:
    """Remove instance attributes added after ``keys_before`` was snapshotted.

    Used so ``unittest.TestCase.setUp`` storage on ``self`` (Traitables, lists of
    them, etc.) does not keep objects alive through isolation's leftover check.
    Safe no-op if ``inst`` is gone or keys were already deleted in ``tearDown``.
    """
    if inst is None:
        return
    for key in set(vars(inst)) - keys_before:
        try:
            delattr(inst, key)
        except Exception:  # noqa: BLE001 — best-effort cleanup before leftover assert
            pass


def reset_traitable_process_state(*, assert_clean: bool = True) -> None:
    """Clear process-global Traitable/XCache state after a test.

    Also clears all ``@core_10x.global_cache.cache`` memos so test-held Traitables
    do not outlive ``XCache.clear()`` (stale origin cache). Domain singletons that
    are not ``@cache`` (e.g. ``PricingContext.s_current_pc``) still need local
    fixture cleanup.

    ``assert_clean`` (default True) fails if any Traitable is still reachable.
    Pass False after a failed test so stack/fixture holders do not add noise on
    top of the original failure.
    """
    Scenario.s_instances.clear()
    _clear_all_caches()
    XCache.clear()
    clear_traitable_store_state()
    gc.collect()

    if not assert_clean:
        return

    # Prefer issubclass(type(obj), ...) over isinstance: gc.get_objects() can include
    # dead weakref.proxy objects, and isinstance() dereferences them (ReferenceError).
    leftovers = [(PyClass.name(obj.__class__), obj.id_value()) for obj in gc.get_objects() if issubclass(type(obj), Traitable)]
    assert not leftovers, leftovers


def pin_current_ts_stores() -> None:
    """Pin main, vault, and every store named on main (NamedTsStore rows).

    Call **just before yield**, after fixture setup has written seed data and
    store associations. Opens main/vault when their URIs are set but cold;
    opens each associated store via ``NamedTsStore.uri`` so in-memory DuckDB
    connections are held across isolation.
    """

    stores = set()
    if vault_pin := (Traitable.vault_store(), EnvVars.main_vault_uri) if EnvVars.main_vault_uri else None:
        stores.add(vault_pin[0])
    if main_pin := (Traitable.main_store(), EnvVars.main_ts_store_uri) if EnvVars.main_ts_store_uri else None:
        stores.add(main_pin[0])
        with main_pin[0]:
            stores.update(Traitable.store_from_uri(n.uri) for n in NamedTsStore.load_many() if n.uri)

    _pin_stack.append(({k: v for k, v in TsStore.s_instances.items() if v in stores}, main_pin, vault_pin))


def unpin_ts_stores() -> None:
    """Pop the most recent pin frame, then reset + restore like test_isolation.

    ``assert_clean=False``: unlike ``dev_10x.pytest_plugin.test_isolation``, this has
    no ``rep_call`` to tell whether the preceding test passed. Asserting here would be
    redundant when it did (per-test isolation already checked) and would pile a
    spurious leftover error onto a real failure when it didn't.
    """
    if not _pin_stack:
        return
    _pin_stack.pop()
    reset_traitable_process_state(assert_clean=False)
    restore_pinned_ts_stores()


def restore_pinned_ts_stores() -> None:
    """Re-publish the **top** pin frame into ``s_instances`` and Traitable caches."""
    if not _pin_stack:
        return

    frame_instances, main, vault = _pin_stack[-1]
    TsStore.s_instances.update(frame_instances)

    if main:
        store, uri = main
        EnvVars.main_ts_store_uri = uri
        Traitable.main_store.value[0] = store

    if vault:
        store, uri = vault
        EnvVars.main_vault_uri = uri
        Traitable.vault_store.value[0] = store


@contextmanager
def pinned_ts_stores() -> Iterator[None]:
    """Context manager: :func:`pin_current_ts_stores` on enter, :func:`unpin_ts_stores` on exit."""
    pin_current_ts_stores()
    try:
        yield
    finally:
        unpin_ts_stores()
