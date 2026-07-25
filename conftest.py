import os

from dev_10x.pytest_plugin import pytest_ignore_collect, test_isolation


def pytest_collection_modifyitems(config, items):
    """Drop the rio browser tests when XX_SKIP_RIO is set (Linux ASan lane).

    Under LD_PRELOAD AddressSanitizer the rio browser client can't start, so every rio test
    times out (setup error) and rio's asyncio-atexit close handler then deadlocks pytest's
    session teardown. `--ignore` can't remove them: dev_10x.pytest_plugin.pytest_ignore_collect
    force-collects every unit_tests dir (returns False) and, as a firstresult hook, overrides the
    built-in ignore. Deselecting post-collection is not overridable, and dropping the whole tree
    means the session-scoped `manage_server` fixture never runs (no browser client, no atexit
    registration). Gated by env var so it only applies where set; Windows ASan and release keep rio.
    """
    if not os.environ.get('XX_SKIP_RIO'):
        return
    keep, dropped = [], []
    for item in items:
        (dropped if item.nodeid.startswith('ui_10x/rio/') else keep).append(item)
    if dropped:
        items[:] = keep
        config.hook.pytest_deselected(items=dropped)
