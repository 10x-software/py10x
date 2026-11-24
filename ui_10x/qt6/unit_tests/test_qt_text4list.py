"""Qt6 counterpart of rio/unit_tests/test_text4list.py."""

from __future__ import annotations

import pytest

from core_10x.exec_control import CACHE_ONLY, INTERACTIVE
from core_10x.traitable import RT, T, Traitable, Ui
from ui_10x.concrete_trait_widgets import TextEditForListWidget
from ui_10x.qt6.testlib import qt_helpers as h
from ui_10x.traitable_editor import TraitableEditor

_LINES: list[str] = []


class _Note(Traitable, keep_history = False):
    name: str           = T(T.ID)
    lines: list[str]    = RT(Ui.text4list('Lines', flags = Ui.READ_ONLY, min_width = 20))

    def lines_get(self) -> list[str]:
        return list(_LINES)


def test_text4list_trait_editor_list_only_and_empty_clears() -> None:
    """text4list accepts list values; empty list clears; non-list raises."""
    _LINES[:] = ['one', 'two']
    with CACHE_ONLY(), INTERACTIVE():
        editor  = TraitableEditor(_Note(name = 'n1'), _confirm = True)  #-- .editor() needs a multi-segment package path
        h.show(editor.main_widget())
        tw = editor.trait_editors['lines'].widget
        assert isinstance(tw, TextEditForListWidget)
        assert tw.to_plain_text() == 'one\ntwo'
        assert tw.widget_value() == ['one', 'two']

        tw.set_widget_value([])
        assert tw.to_plain_text() == ''
        assert tw.widget_value() == []

        with pytest.raises(TypeError, match = 'list is expected'):
            tw._set_value('not-a-list')

        tw.set_widget_value(['alpha', 'beta'])
        assert tw.document().toPlainText() == 'alpha\nbeta'
