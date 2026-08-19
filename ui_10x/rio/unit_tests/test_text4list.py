"""Rio tests for Ui.text4list → TextEditForListWidget."""

from __future__ import annotations

import asyncio

import pytest
import rio.testing
from core_10x.exec_control import CACHE_ONLY, INTERACTIVE
from core_10x.traitable import RT, T, Traitable, Ui
from ui_10x.concrete_trait_widgets import TextEditForListWidget
from ui_10x.rio.browser_helpers import UI_SETTLE_S, wait_for_js_value
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.traitable_editor import TraitableEditor

_LINES: list[str] = []


class _Note(Traitable, keep_history=False):
    name: str = T(T.ID)
    lines: list[str] = RT(Ui.text4list('Lines', flags=Ui.READ_ONLY, min_width=20))

    def lines_get(self) -> list[str]:
        return list(_LINES)


TEXTAREA_VALUE_JS = 'document.querySelector("textarea")?.value ?? ""'


async def test_text4list_trait_editor_list_only_and_empty_clears() -> None:
    """text4list accepts list values; empty list clears; non-list asserts."""
    global _LINES
    _LINES = ['one', 'two']

    with CACHE_ONLY(), INTERACTIVE():
        note = _Note(name='n1')
        # Direct ctor — TraitableEditor.editor() needs a multi-segment package path.
        editor = TraitableEditor(note, _confirm=True)
        root = editor.main_widget()
        tw = editor.trait_editors['lines'].widget
        assert isinstance(tw, TextEditForListWidget)
        assert tw.to_plain_text() == 'one\ntwo'
        assert tw.widget_value() == ['one', 'two']

        tw.set_widget_value([])
        assert tw.to_plain_text() == ''
        assert tw.widget_value() == []

        with pytest.raises(AssertionError, match='list is expected'):
            tw._set_value('not-a-list')

        tw.set_widget_value(['alpha', 'beta'])

    async with rio.testing.BrowserClient(lambda: DynamicComponent(root)) as client:
        await asyncio.sleep(UI_SETTLE_S)
        await wait_for_js_value(client, TEXTAREA_VALUE_JS, 'alpha\nbeta')

        tw.set_widget_value([])
        await client.wait_for_refresh()
        await wait_for_js_value(client, TEXTAREA_VALUE_JS, '')

        tw.set_widget_value(['again'])
        await client.wait_for_refresh()
        await wait_for_js_value(client, TEXTAREA_VALUE_JS, 'again')
