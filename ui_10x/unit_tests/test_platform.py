import sys

import pytest


def test_platform_import_raises(monkeypatch):
    monkeypatch.delitem(sys.modules, 'ui_10x.platform', raising=False)
    with pytest.raises(ImportError):  # raises due to incorrect UI_PLATFORM from conftest
        import ui_10x.platform  # noqa: F401
