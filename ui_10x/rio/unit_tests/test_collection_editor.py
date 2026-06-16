import asyncio
from datetime import date

import pytest
import rio
import rio.testing.browser_client
from core_10x.code_samples.person import Person
from core_10x.exec_control import CACHE_ONLY, INTERACTIVE
from ui_10x.collection_editor import Collection, CollectionEditor
from ui_10x.rio.browser_helpers import (
    COLLECTION_EDITOR_TIMEOUT_MS,
    UI_SETTLE_S,
    press_rio_button,
    wait_for_dialog_button,
    wait_for_input_values,
    wait_for_js_value,
    wait_for_selectable_item_text,
)
from ui_10x.rio.component_builder import DynamicComponent

_CE_TIMEOUT = COLLECTION_EDITOR_TIMEOUT_MS


@pytest.fixture(autouse=True)
def mock_db_ops(monkeypatch):
    with CACHE_ONLY():
        sasha = Person(first_name='Sasha', last_name='Davidovich', weight_lbs=150, _replace=True)
        ilya = Person(first_name='Ilya', last_name='Pevzner', weight_lbs=200, dob=date(1971, 7, 3), _replace=True)
    monkeypatch.setattr(Person, 'load_ids', lambda: [sasha.id(), ilya.id()])
    monkeypatch.setattr(Person, 'load_data', lambda id: {sasha.id(): sasha, ilya.id(): ilya}[id])
    yield


@pytest.fixture(autouse=True)
def interactive_mode():
    interactive = INTERACTIVE()
    interactive.begin_using()
    yield
    interactive.end_using()


async def test_collection_editor() -> None:
    coll = Collection(cls=Person)
    ce = CollectionEditor(coll=coll)
    widget = ce.main_widget()

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(UI_SETTLE_S)

        await wait_for_js_value(
            test_client,
            'document.querySelector(".rio-selectable-item")?.innerText || ""',
            'Ilya|Pevzner',
            timeout_ms=_CE_TIMEOUT,
        )
        await test_client.execute_js('document.querySelector(".rio-selectable-item").click()')
        await asyncio.sleep(UI_SETTLE_S)

        await wait_for_input_values(
            test_client,
            weight_index=7,
            weight='200.00',
            unit_index=8,
            unit='LB',
            timeout_ms=_CE_TIMEOUT,
        )

        edit_button = next(b for b in test_client.get_components(rio.Button) if b.content == 'edit')
        await press_rio_button(test_client, edit_button)
        await wait_for_dialog_button(test_client, 'Ok', timeout_ms=_CE_TIMEOUT)
        await asyncio.sleep(UI_SETTLE_S)

        await wait_for_input_values(
            test_client,
            weight_index=15,
            weight='200.00',
            unit_index=16,
            unit='LB',
            timeout_ms=_CE_TIMEOUT,
        )

        dropdown_button = next(
            b for b in reversed(tuple(test_client.get_components(rio.Button))) if b.icon == 'material/arrow_downward'
        )
        await press_rio_button(test_client, dropdown_button)
        await wait_for_selectable_item_text(test_client, 'G', timeout_ms=_CE_TIMEOUT)
        await asyncio.sleep(UI_SETTLE_S)

        list_item_id = next(li._id_ for li in test_client.get_components(rio.SimpleListItem) if li.text == 'G')
        await test_client.execute_js(
            f'''document.querySelector('[dbg-id="{list_item_id}"]').querySelector('.rio-selectable-item').click()'''
        )
        await asyncio.sleep(UI_SETTLE_S)

        await wait_for_input_values(
            test_client,
            weight_index=15,
            weight='90,702.95',
            unit_index=16,
            unit='G',
            timeout_ms=_CE_TIMEOUT,
        )

        ok_button = next(b for b in test_client.get_components(rio.Button) if b.content == 'Ok')
        await press_rio_button(test_client, ok_button)
        await asyncio.sleep(UI_SETTLE_S)

        await wait_for_input_values(
            test_client,
            weight_index=7,
            weight='90,702.95',
            unit_index=8,
            unit='G',
            timeout_ms=_CE_TIMEOUT,
        )
