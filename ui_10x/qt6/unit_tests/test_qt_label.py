"""Qt6 counterpart of rio/widgets/unit_tests/test_label.py."""

import ui_10x.qt6.platform_implementation as ux
from ui_10x.qt6.testlib import qt_helpers as h


def test_label() -> None:
    widget = h.show(ux.Label('Hello World'))
    assert widget.text() == 'Hello World'

    widget.set_text('Updated Text')
    assert widget.text() == 'Updated Text'


def test_label_empty() -> None:
    widget = h.show(ux.Label())
    assert widget.text() == ''

    widget.set_text('New Text')
    assert widget.text() == 'New Text'
