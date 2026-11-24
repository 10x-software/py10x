import pytest

pytest.register_assert_rewrite('ui_10x.testlib')


@pytest.fixture(autouse = True)
def setup_ui_platform(monkeypatch):
    monkeypatch.setenv('UI_PLATFORM', 'Unknown')
    yield
    monkeypatch.undo()
