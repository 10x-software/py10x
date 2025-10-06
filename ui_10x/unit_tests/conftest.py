import pytest


@pytest.fixture(autouse=True)
def setup_ui_platform(monkeypatch):
    monkeypatch.setenv('UI_PLATFORM', 'Unknown')
    yield
    monkeypatch.undo()
