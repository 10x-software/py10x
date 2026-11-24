"""Qt6 counterpart of rio/widgets/unit_tests/test_button.py."""

import ui_10x.qt6.platform_implementation as ux
from ui_10x.qt6.testlib import qt_helpers as h


def _button(text: str) -> tuple[ux.PushButton, list]:
    clicks = []
    widget = ux.PushButton(text)
    widget.clicked_connect(lambda: clicks.append(True))
    return h.show(widget), clicks


def test_button_comprehensive() -> None:
    widget, clicks = _button('Click Me')
    assert widget.text() == 'Click Me'

    h.click(widget)
    assert clicks == [True]

    h.click(widget)
    assert len(clicks) == 2


def test_button_disabled_interaction() -> None:
    widget, clicks = _button('Test Button')
    h.click(widget)
    assert len(clicks) == 1

    widget.set_enabled(False)
    assert not widget.is_enabled()
    h.click(widget)
    assert len(clicks) == 1

    widget.set_enabled(True)
    assert widget.is_enabled()
    h.click(widget)
    assert len(clicks) == 2


def test_button_basic_functionality() -> None:
    widget, _ = _button('Test Button')
    assert widget.text() == 'Test Button'
    assert widget.is_enabled()

    assert not widget.is_flat()
    widget.set_flat(True)
    assert widget.is_flat()
