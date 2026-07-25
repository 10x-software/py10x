import contextlib
import os

import pytest
import rio.testing.browser_client


@contextlib.contextmanager
def _drop_ld_preload():
    """Remove LD_PRELOAD across the browser-spawn window (no-op when unset).

    Under ASan the suite runs with LD_PRELOAD=libasan, which Playwright's node driver and Chromium
    would inherit and hang on. Dropping it for the spawn lets the browser exec clean; the main
    process keeps its already-mapped libasan (clearing the env var doesn't unload it) once restored.
    """
    saved = os.environ.pop('LD_PRELOAD', None)
    try:
        yield
    finally:
        if saved is not None:
            os.environ['LD_PRELOAD'] = saved


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

    # Browser processes are only spawned on enter, so strip LD_PRELOAD just for that.
    cm = rio.testing.browser_client.prepare_browser_client()
    with _drop_ld_preload():
        await cm.__aenter__()
    try:
        yield
    finally:
        await cm.__aexit__(None, None, None)


@pytest.fixture(autouse=True)
def setup_ui_platform(monkeypatch):
    monkeypatch.setenv('UI_PLATFORM', 'Rio')
    yield
    monkeypatch.undo()
