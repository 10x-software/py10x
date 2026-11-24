"""Qt6 counterpart of rio/widgets/unit_tests/test_checkbox.py."""

import ui_10x.qt6.platform_implementation as ux
from ui_10x.qt6.testlib import qt_helpers as h


def test_checkbox_comprehensive() -> None:
    states = []
    widget = ux.CheckBox('Check me')
    widget.state_changed_connect(states.append)
    h.show(widget)
    assert widget.text() == 'Check me'
    assert not widget.is_checked()

    h.click(widget)
    assert widget.is_checked()
    assert states == [ux.Qt.CheckState.Checked.value]

    widget.set_checked(False)
    assert not widget.is_checked()

    h.click(widget)
    assert widget.is_checked()


def test_checkbox_disabled_interaction() -> None:
    widget = h.show(ux.CheckBox('Test Checkbox'))
    h.click(widget)
    assert widget.is_checked()

    widget.set_enabled(False)
    h.click(widget)
    assert widget.is_checked()

    widget.set_enabled(True)
    h.click(widget)
    assert not widget.is_checked()


def test_checkbox_basic_functionality() -> None:
    widget = h.show(ux.CheckBox('Test Checkbox'))
    assert not widget.is_checked()

    widget.set_checked(True)
    assert widget.is_checked()

    widget.set_checked(False)
    assert not widget.is_checked()

    widget.set_enabled(False)
    assert not widget.is_enabled()
    widget.set_enabled(True)
    assert widget.is_enabled()
