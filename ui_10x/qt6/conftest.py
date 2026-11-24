import pytest


class QtModule(pytest.Module):
    """A Qt test module: imported, as its tests are run, on the Qt-bound generic ui_10x modules (see qt_helpers)."""

    def collect(self):
        from ui_10x.qt6.testlib import qt_helpers  #-- where Qt doesn't load: skips the module, or fails it under XX_TEST_STRICT

        with qt_helpers.qt_backend():
            return list(super().collect())


def pytest_pycollect_makemodule(module_path, parent):
    return QtModule.from_parent(parent, path = module_path)


@pytest.fixture(autouse = True)
def setup_ui_platform(monkeypatch):
    monkeypatch.setenv('UI_PLATFORM', 'Qt6')
    yield
    monkeypatch.undo()


@pytest.fixture(autouse = True)
def qt_ui():
    """Runs each test on the Qt-bound modules; it leaves no window behind, and an error in a slot fails it."""
    from ui_10x.qt6.testlib import qt_helpers

    qt_helpers.app()
    with qt_helpers.qt_backend(), qt_helpers.slot_errors():
        try:
            yield
        finally:
            qt_helpers.release_widgets()
