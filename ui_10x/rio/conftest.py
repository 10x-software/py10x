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

    async with rio.testing.browser_client.prepare_browser_client():
        yield


@pytest.fixture(autouse=True)
def setup_ui_platform(monkeypatch):
    monkeypatch.setenv('UI_PLATFORM', 'Rio')
    yield
    monkeypatch.undo()
