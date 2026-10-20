"""Rio coverage for MultiChoice (flat list select / deselect)."""

from __future__ import annotations

import asyncio

import rio.testing.browser_client
from core_10x.code_samples.directories import ANIMALS
from ui_10x.choice import MultiChoice
from ui_10x.rio.browser_helpers import (
    UI_SETTLE_S,
    wait_for_list_item_count,
    wait_for_selectable_item_text,
)
from ui_10x.rio.component_builder import DynamicComponent

import rio


def test_multi_choice_flat_select_deselect() -> None:
    mc = MultiChoice(choices=['Alpha', 'Beta', 'Gamma'])
    assert mc.widget() is not None

    mc.on_item_selected(None, 'Alpha', True)
    assert mc.values_selected == ['Alpha']
    assert mc.selection_list.child_count() == 1

    item = mc.selection_list.get_children()[0]
    assert item.text() == 'Alpha'

    mc.on_selection_list_selection(item)
    assert mc.values_selected == []
    assert mc.selection_list.child_count() == 0


def test_multi_choice_directory_builds() -> None:
    mc = MultiChoice(choices=ANIMALS)
    widget = mc.widget()
    assert widget is not None
    # Selection mode radios only appear for Directory / tree source.
    assert mc.rb is not None
    assert mc.rb.choice() is not None


async def test_multi_choice_flat_browser_select_deselect() -> None:
    """Click source list to select, then selection list to deselect."""
    mc = MultiChoice(choices=['Alpha', 'Beta', 'Gamma'])
    widget = mc.widget()

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(UI_SETTLE_S)
        await wait_for_list_item_count(test_client, 3)
        await wait_for_selectable_item_text(test_client, 'Alpha')

        # Source list is the only 'Alpha' until a selection is made.
        await test_client.execute_js(
            """(() => {
                for (const el of document.querySelectorAll('.rio-selectable-item')) {
                    if (el.innerText === 'Alpha') { el.click(); return; }
                }
            })()"""
        )
        await asyncio.sleep(UI_SETTLE_S)

        assert mc.values_selected == ['Alpha']
        assert mc.selection_list.child_count() == 1
        # Source (3) + selection pane (1)
        await wait_for_list_item_count(test_client, 4)

        # Second 'Alpha' is the selection-pane copy — click it to remove.
        await test_client.execute_js(
            """(() => {
                const matches = [...document.querySelectorAll('.rio-selectable-item')]
                    .filter(el => el.innerText === 'Alpha');
                matches[matches.length - 1].click();
            })()"""
        )
        await asyncio.sleep(UI_SETTLE_S)

        assert mc.values_selected == []
        assert mc.selection_list.child_count() == 0
        await wait_for_list_item_count(test_client, 3)


async def test_multi_choice_directory_browser_select_deselect() -> None:
    """Directory tree: click an item to select, then click selection pane to remove."""
    mc = MultiChoice(choices=ANIMALS)
    widget = mc.widget()
    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(UI_SETTLE_S)
        assert mc.rb is not None
        assert mc.selection_list is not None
        assert mc.rb['title'] == 'Selection Mode'
        assert await test_client.playwright_page.get_by_text('Selection Mode', exact=True).count() == 1
        assert await test_client.playwright_page.get_by_text('Animals', exact=True).count() == 1

        from rio.components.error_placeholder import ErrorPlaceholder

        errors = list(test_client.get_components(ErrorPlaceholder))
        assert not errors, f'tree failed to build: {[e.error_summary for e in errors]}'
        texts = {getattr(item.content, 'text', None) for item in test_client.get_components(rio.SimpleTreeItem)}
        assert 'Microorganisms' in texts
        assert 'Salt Water' in texts  # single-child parent must keep its own label
        assert 'Mollusks' in texts

        # Tree labels are not .rio-selectable-item; click the visible text.
        await test_client.playwright_page.get_by_text('Mollusks', exact=True).click()
        await asyncio.sleep(UI_SETTLE_S)

        assert mc.values_selected == ['Mollusks']
        assert mc.selection_list.child_count() == 1
        assert mc.selection_list.get_children()[0].text() == 'Mollusks'
        await wait_for_selectable_item_text(test_client, 'Mollusks')

        # Selection pane ListWidget copy — second exact 'Mollusks' in the page.
        await test_client.playwright_page.get_by_text('Mollusks', exact=True).nth(1).click()
        await asyncio.sleep(UI_SETTLE_S)

        assert mc.values_selected == []
        assert mc.selection_list.child_count() == 0

        # LEAF mode: parent nodes must not be added; leaf nodes may.
        # Parent click still expands so children become reachable.
        await test_client.playwright_page.get_by_text('LEAF', exact=True).click()
        await asyncio.sleep(UI_SETTLE_S)
        assert mc.select_mode() is mc.SELECT_MODE.LEAF

        await test_client.playwright_page.get_by_text('Mammals', exact=True).click()
        await asyncio.sleep(UI_SETTLE_S)
        assert mc.values_selected == []
        assert await test_client.playwright_page.get_by_text('Cats', exact=True).count() >= 1

        await test_client.playwright_page.get_by_text('Mollusks', exact=True).click()
        await asyncio.sleep(UI_SETTLE_S)
        assert mc.values_selected == ['Mollusks']


async def test_multi_choice_directory_subdir_mode() -> None:
    """SUBDIR replaces selected children when a parent is chosen."""
    mc = MultiChoice(choices=ANIMALS)
    widget = mc.widget()

    def expand(item) -> None:
        item['is_expanded'] = True
        for child in item.get_children():
            expand(child)

    for i in range(mc.sw.top_level_item_count()):
        expand(mc.sw.top_level_item(i))

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(UI_SETTLE_S)
        page = test_client.playwright_page

        await page.get_by_text('SUBDIR', exact=True).click()
        await asyncio.sleep(UI_SETTLE_S)
        assert mc.select_mode() is mc.SELECT_MODE.SUBDIR

        await page.get_by_text('Cats', exact=True).click()
        await asyncio.sleep(UI_SETTLE_S)
        await page.get_by_text('Dogs', exact=True).click()
        await asyncio.sleep(UI_SETTLE_S)
        assert mc.values_selected == ['Cats', 'Dogs']

        await page.get_by_text('Mammals', exact=True).click()
        await asyncio.sleep(UI_SETTLE_S)
        assert mc.values_selected == ['Mammals']
        assert [c.text() for c in mc.selection_list.get_children()] == ['Mammals']

        await page.get_by_text('Cats', exact=True).click()
        await asyncio.sleep(UI_SETTLE_S)
        assert mc.values_selected == ['Mammals']
