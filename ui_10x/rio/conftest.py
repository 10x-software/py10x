import contextlib
import os

import pytest
import rio.testing.browser_client


@contextlib.contextmanager
def _drop_ld_preload():
    """Remove LD_PRELOAD for the duration of the block (the browser-subprocess spawn window).

    Under AddressSanitizer the suite runs with LD_PRELOAD=libasan..., which every child process
    inherits - including Playwright's node driver and the uninstrumented Chromium it launches, which
    then hang/time out. Every browser spawn happens while entering prepare_browser_client(), so drop
    LD_PRELOAD just for that: the browser execs with a clean environment, the main process keeps its
    already-mapped libasan (clearing the env var does not unload it), and tests that spawn
    py10x_kernel subprocesses still see LD_PRELOAD once it is restored. No-op when unset.
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

    # Spawn the browser (node driver + Chromium) with LD_PRELOAD stripped, then restore it so the
    # rest of the session runs instrumented as usual. Browser processes are only spawned on enter.
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
