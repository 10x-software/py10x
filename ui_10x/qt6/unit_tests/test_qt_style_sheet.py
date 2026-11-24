"""Qt6 counterpart of rio/unit_tests/test_style_sheet_page.py: ``style_sheet.__main__``, a TraitableEditor popup."""

from core_10x.exec_control import INTERACTIVE
from ui_10x.examples.style_sheet import StyleSheet
from ui_10x.qt6.testlib import qt_helpers as h
from ui_10x.traitable_editor import TraitableEditor


def test_style_sheet_editor_renders_wysiwyg() -> None:
    def check(d):
        assert 'WYSIWYG' in [label.text() for label in d.findChildren(h.QWidget) if hasattr(label, 'text') and isinstance(label.text(), str)]
        assert 'This is how it will look...' in h.texts(d)
        h.click(h.button(d, 'Cancel'))

    with INTERACTIVE():
        h.run_modal(TraitableEditor(StyleSheet(), _confirm = True).popup, check)
