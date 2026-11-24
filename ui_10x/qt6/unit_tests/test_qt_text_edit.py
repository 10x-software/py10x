"""What TextEditWidget writes back when it loses focus (Rio: rio/unit_tests/test_text_edit_focus_out.py)."""

import pytest

from core_10x.exec_control import CACHE_ONLY, INTERACTIVE
from core_10x.traitable import RT, T, Traitable, Ui
from ui_10x.qt6.testlib import qt_helpers as h
from ui_10x.traitable_editor import TraitableEditor


class _Text(Traitable, keep_history = False):
    name: str           = T(T.ID)
    n: int              = RT(1)
    text: str           = RT(Ui.text('Text'))
    read_only: str      = RT(Ui.text('Read only', flags = Ui.READ_ONLY))
    lines: list[str]    = RT(Ui.text4list('Lines'))

    def text_get(self) -> str:
        return f'text {self.n}'

    def read_only_get(self) -> str:
        return f'read only {self.n}'

    def lines_get(self) -> list[str]:
        return [f'line {self.n}']


def _shown(obj: _Text):
    """The editor's main widget, to be kept, and its trait widgets by trait name."""
    root = h.show(TraitableEditor(obj, _confirm = True).main_widget())  #-- .editor() needs a multi-segment package path
    return root, h.trait_widgets(root)


def _type(widget, text: str) -> None:
    h.focus(widget)
    widget.selectAll()
    h.QTest.keyClick(widget, h.Qt.Key.Key_Delete)
    for i, line in enumerate(text.split('\n')):
        if i:
            h.QTest.keyClick(widget, h.Qt.Key.Key_Return)  #-- keyClicks() can't type a line break
        h.QTest.keyClicks(widget, line)


def _lose_focus(widgets) -> None:
    h.focus(widgets['name'])


def test_an_edit_is_committed_on_focus_out() -> None:
    with CACHE_ONLY(), INTERACTIVE():
        obj             = _Text(name = 'a')
        _root, widgets  = _shown(obj)
        _type(widgets['text'], 'typed')
        assert obj.text == 'text 1'

        _lose_focus(widgets)
        assert obj.text == 'typed'


def test_a_list_edit_is_committed() -> None:
    with CACHE_ONLY(), INTERACTIVE():
        obj             = _Text(name = 'a')
        _root, widgets  = _shown(obj)
        _type(widgets['lines'], 'one\ntwo')
        _lose_focus(widgets)
        assert obj.lines == ['one', 'two']


def test_clearing_restores_the_computed_value() -> None:
    with CACHE_ONLY(), INTERACTIVE():
        obj             = _Text(name = 'a')
        _root, widgets  = _shown(obj)
        _type(widgets['text'], 'typed')
        _lose_focus(widgets)
        assert obj.text == 'typed'

        _type(widgets['text'], '')
        _lose_focus(widgets)
        assert obj.text == 'text 1'


@pytest.mark.parametrize('name', ['text', 'read_only', 'lines'])
def test_losing_focus_unedited_leaves_the_value_computed(name) -> None:
    with CACHE_ONLY(), INTERACTIVE():
        obj             = _Text(name = 'a')
        _root, widgets  = _shown(obj)
        h.focus(widgets[name])
        assert widgets[name].hasFocus()

        _lose_focus(widgets)
        assert not obj.is_set(obj.trait(name))
        obj.n = 2
        h.app().processEvents()  #-- the refresh is queued
        assert '2' in widgets[name].to_plain_text()
