"""Smoke tests for minimal Rio TableView (guess_word Phase 1)."""

from __future__ import annotations

import asyncio
import gc
import sys

import rio.testing.browser_client
from core_10x.exec_control import CACHE_ONLY
from core_10x.traitable import RT, T, Traitable, Ui
from ui_10x.rio.browser_helpers import UI_SETTLE_S, wait_for_js_truthy
from ui_10x.rio.widgets.table import TableView
import ui_10x.platform_interface as i

import rio


class StyledCell(Traitable):
    letter: str = T(Ui(label='L'))
    bg: str = RT(T.HIDDEN, default='lightgray')
    fg: str = RT(T.HIDDEN, default='black')

    def letter_style_sheet(self):
        return T.colors(self.bg, self.fg)


def test_table_view_construct_and_render() -> None:
    with CACHE_ONLY():
        rows = [
            StyledCell(letter='A', bg='darkgreen', fg='white'),
            StyledCell(letter='B'),
        ]

        table = TableView(rows)
        assert isinstance(table, i.TableView)
        assert table.trait_names == ['letter']
        assert table.header_labels == ['L']
        table.horizontalHeader().setStretchLastSection(False)

        text, sh = table._cell_text_and_style(rows[0], 'letter')
        assert text == 'A'
        assert 'darkgreen' in sh
        assert 'white' in sh

        rows[1].letter = 'Z'
        rows[1].bg = 'white'
        rows[1].fg = 'black'
        table.render_traitable(1, None)
        text2, sh2 = table._cell_text_and_style(table.entities[1], 'letter')
        assert text2 == 'Z'
        assert 'background-color: white' in sh2

        table.entities.clear()
        del table, rows


async def test_table_view_browser_render_traitable() -> None:
    """Update cells while the table is nested under a host (same as ``rio run``)."""
    with CACHE_ONLY():
        row = StyledCell(letter='X')
        table = TableView([row])

        def host_factory(_table=table):
            class Host(rio.Component):
                def build(self) -> rio.Component:
                    return _table()

            return Host()

        try:
            async with rio.testing.BrowserClient(host_factory) as test_client:
                await asyncio.sleep(UI_SETTLE_S)
                await wait_for_js_truthy(
                    test_client,
                    """(() => {
                        const texts = [...document.querySelectorAll('.rio-text')]
                            .map(el => el.children[0]?.innerText || '');
                        return texts.includes('X') && texts.includes('L');
                    })()""",
                )

                row.letter = 'Y'
                row.bg = 'darkgreen'
                row.fg = 'white'
                table.render_traitable(0, None)
                await test_client.wait_for_refresh()
                await asyncio.sleep(UI_SETTLE_S)

                await wait_for_js_truthy(
                    test_client,
                    """(() => {
                        const texts = [...document.querySelectorAll('.rio-text')]
                            .map(el => el.children[0]?.innerText || '');
                        return texts.includes('Y') && !texts.includes('X');
                    })()""",
                )
        finally:
            table.entities.clear()
            table.component = None
            table.subcomponent = None
            del table, row
            gc.collect()


def test_table_view_dispatcher_rio() -> None:
    """``ui_10x.table_view`` follows the Rio impl and must not pull table_header_view."""
    for mod in list(sys.modules):
        if mod == 'ui_10x.table_view' or mod.startswith('ui_10x.qt6.table_view'):
            del sys.modules[mod]
    sys.modules.pop('ui_10x.table_header_view', None)

    import ui_10x.table_view as tv

    assert tv.TableView is TableView
    assert 'ui_10x.table_header_view' not in sys.modules
    assert 'ui_10x.qt6.table_view' not in sys.modules
