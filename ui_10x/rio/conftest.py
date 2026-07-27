import os

import pytest
import rio.testing.browser_client


def running_with_coverage(config):
    if not config.pluginmanager.getplugin('pytest_cov'):
        return False

    if not config.getoption('--cov', default='COV_CORE_SOURCE' in os.environ):
        return False

    return not config.getoption('--no-cov', default=False)


@pytest.fixture(scope='session', autouse=True)
async def manage_server(request):
    if running_with_coverage(request.config):
        # run headless client even if running with coverage
        rio.testing.browser_client.DEBUGGER_ACTIVE = False
        pytest.mark.async_timeout(180)
    else:
        if rio.testing.browser_client.DEBUGGER_ACTIVE:
            pytest.mark.async_timeout(0 if rio.testing.browser_client.DEBUGGER_ACTIVE else 90)

    # Under ASan the suite runs with LD_PRELOAD=libasan; Playwright's node driver and Chromium would
    # inherit it and hang. Drop it while the browser client is alive so the browser execs clean (the
    # main process keeps its already-mapped libasan). Safe because no test that collects after
    # ui_10x/rio spawns a py10x_kernel subprocess (which would need libasan preloaded to import).
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
