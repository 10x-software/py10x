import os

import pytest
import rio.icon_registry as rio_icon_registry
import rio.testing.browser_client
import rio.utils


def running_with_coverage(config):
    if not config.pluginmanager.getplugin('pytest_cov'):
        return False

    if not config.getoption('--cov', default='COV_CORE_SOURCE' in os.environ):
        return False

    return not config.getoption('--no-cov', default=False)


@pytest.fixture(scope='session', autouse=True)
def isolate_rio_icon_cache() -> None:
    # A cache per worker, because rio reads "directory exists" as "set is extracted" while
    # extractall is still writing 6k files into it -- workers sharing one cache race that.
    manager = rio.utils.ASSET_MANAGER
    version = manager._versioned_cache_dir.name
    manager.cache_dir = manager.cache_dir.parent / 'rio-py10x-test' / os.environ.get('PYTEST_XDIST_WORKER', 'main')
    manager._versioned_cache_dir = manager.cache_dir / version

    # Whole sets, never a list of icon names: the ones that break a build are pulled in by
    # rio's own components (TreeView -> arrow_drop_down), so any list here rots on upgrade.
    for set_name in rio_icon_registry.all_icon_sets():
        rio_icon_registry._ensure_icon_set_is_extracted(set_name)


@pytest.fixture(scope='session')
def session_default_async_timeout(pytestconfig) -> float:
    if running_with_coverage(pytestconfig):
        return 180.0
    if rio.testing.browser_client.DEBUGGER_ACTIVE:
        # Effectively no limit; a literal 0 arms call_later(0, ...) and fires at once.
        return 86400.0
    return 90.0


@pytest.fixture(scope='session', autouse=True)
async def manage_server(request):

    if running_with_coverage(request.config):
        # run headless client even if running with coverage
        rio.testing.browser_client.DEBUGGER_ACTIVE = False

    # Drop any LD_PRELOAD used by address sanitizer tests to avoid playwright/chromium hangs
    saved = os.environ.pop('LD_PRELOAD', None)
    try:
        async with rio.testing.browser_client.prepare_browser_client():
            yield
    finally:
        if saved is not None:
            os.environ['LD_PRELOAD'] = saved


@pytest.fixture(autouse=True)
def setup_ui_platform(monkeypatch):
    monkeypatch.setenv('UI_PLATFORM', 'Rio')
    yield
    monkeypatch.undo()
