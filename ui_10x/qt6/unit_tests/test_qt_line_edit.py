"""Qt6 counterpart of rio/widgets/unit_tests/test_line_edit.py."""

from PyQt6.QtCore import QPoint, Qt

from core_10x.exec_control import CACHE_ONLY, INTERACTIVE
from core_10x.traitable import T, Traitable

import ui_10x.platform_interface as i
import ui_10x.qt6.platform_implementation as ux
from ui_10x.qt6.testlib import qt_helpers as h
from ui_10x.traitable_editor import TraitableEditor


class _Named(Traitable, keep_history = False):
    name: str = T(T.ID)


def test_line_edit_comprehensive() -> None:
    edited, finished    = [], []
    widget              = ux.LineEdit('Initial Text')
    widget.text_edited_connect(edited.append)
    widget.editing_finished_connect(lambda: finished.append(True))
    h.show(widget)
    assert widget.text() == 'Initial Text'

    h.type_text(widget, 'User Typed Text', commit = False)
    assert widget.text() == 'User Typed Text'
    assert edited[-1] == 'User Typed Text'  #-- Qt reports every keystroke, Rio the debounced value
    assert not finished

    widget.clearFocus()
    assert finished == [True]

    count = len(edited)
    widget.set_text('Widget Updated')
    assert widget.text() == 'Widget Updated'
    assert len(edited) == count, 'a programmatic change is not an edit'

    widget.set_tool_tip('Helpful tip')
    assert widget.tool_tip() == 'Helpful tip'

    assert widget.echo_mode() == ux.LineEdit.EchoMode.Normal
    widget.set_password_mode()
    assert widget.echo_mode() == ux.LineEdit.EchoMode.Password


def test_line_edit_disabled_interaction() -> None:
    edited = []
    widget = ux.LineEdit('Initial Text')
    widget.text_edited_connect(edited.append)
    h.show(widget)

    h.type_text(widget, 'A')
    assert widget.text() == 'A'
    assert edited[-1] == 'A'

    widget.set_enabled(False)
    count = len(edited)
    h.type_text(widget, 'B')
    assert widget.text() == 'A'
    assert len(edited) == count

    widget.set_enabled(True)
    h.type_text(widget, 'C')
    assert widget.text() == 'C'
    assert edited[-1] == 'C'


def test_line_edit_mouse_press_event_override() -> None:
    """An override gets each press; what it passes on to the base behaves as usual, e.g. places the cursor."""
    presses = []

    class MyLineEdit(ux.LineEdit):
        def mouse_press_event(self, event: i.MouseEvent):
            presses.append('right' if event.is_right_button() else 'left')
            if event.is_left_button():
                ux.LineEdit.mouse_press_event(self, event)

    widget = h.show(MyLineEdit('Initial Text'))
    widget.setCursorPosition(0)
    h.click(widget, Qt.MouseButton.RightButton)
    assert presses == ['right']
    assert widget.cursorPosition() == 0

    h.click(widget, pos = QPoint(widget.width() - 3, widget.height() // 2))
    assert presses == ['right', 'left']
    assert widget.cursorPosition() == len('Initial Text')


def test_event_handler_of_a_base_class_is_kept() -> None:
    presses = []

    class MyLineEdit(ux.LineEdit):
        def mouse_press_event(self, event: i.MouseEvent):
            presses.append(event)

    class MyOtherLineEdit(MyLineEdit): ...

    h.click(h.show(MyOtherLineEdit('x')))
    assert len(presses) == 1


def test_line_edit_trait_widget_takes_clicks() -> None:
    with CACHE_ONLY(), INTERACTIVE():
        editor  = TraitableEditor(_Named(name = 'abc'), _confirm = True)
        root    = h.show(editor.main_widget())
        widget  = h.trait_widgets(root)['name']
        widget.setCursorPosition(0)
        h.click(widget, Qt.MouseButton.RightButton)
        h.click(widget, pos = QPoint(widget.width() - 3, widget.height() // 2))
        assert widget.cursorPosition() == 3


def test_line_edit_editing_finished() -> None:
    """Qt: on Enter, and on losing focus after a change; Rio: whenever focus is lost."""
    finished    = []
    widget      = ux.LineEdit('x')
    widget.editing_finished_connect(lambda: finished.append(True))
    h.show(widget)
    h.focus(widget)
    widget.clearFocus()
    assert not finished

    h.type_text(widget, 'y')
    assert len(finished) == 1

    h.focus(widget)
    h.QTest.keyClick(widget, Qt.Key.Key_Return)
    assert len(finished) == 2
