import asyncio
import gc
import weakref
from datetime import date

import pytest
import rio.testing.browser_client
from core_10x.code_samples.person import Person
from core_10x.exec_control import BTP, CACHE_ONLY, INTERACTIVE
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
from ui_10x.rio.component_builder import DynamicComponent, UserSessionContext, session_context

import rio

_CE_TIMEOUT = COLLECTION_EDITOR_TIMEOUT_MS


@pytest.fixture
def mock_db_ops(monkeypatch):
    with CACHE_ONLY():
        sasha = Person(first_name='Sasha', last_name='Davidovich', weight_lbs=150, _replace=True)
        ilya = Person(first_name='Ilya', last_name='Pevzner', weight_lbs=200, dob=date(1971, 7, 3), _replace=True)
    monkeypatch.setattr(Person, 'load_ids', lambda: [sasha.id(), ilya.id()])
    monkeypatch.setattr(Person, 'load_data', lambda id: {sasha.id(): sasha, ilya.id(): ilya}[id])
    yield


async def test_collection_editor(mock_db_ops) -> None:
    with INTERACTIVE():
        ce: CollectionEditor | None = None
        widget = None

        def on_session_start(session):
            nonlocal ce, widget
            ctx = UserSessionContext()
            ctx.interactive = BTP.current()
            session.attach(ctx)
            with session_context(session):
                ce = CollectionEditor(coll=Collection(cls=Person))
                widget = ce.main_widget()

        app = rio.App(
            name='collection_editor_test',
            build=lambda: DynamicComponent(widget),
            on_session_start=on_session_start,
        )
        async with rio.testing.BrowserClient(app) as test_client:
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

            dropdown_button = next(b for b in reversed(tuple(test_client.get_components(rio.Button))) if b.icon == 'material/arrow_downward')
            await press_rio_button(test_client, dropdown_button)
            await wait_for_selectable_item_text(test_client, 'G', timeout_ms=_CE_TIMEOUT)
            await asyncio.sleep(UI_SETTLE_S)

            list_item_id = next(li._id_ for li in test_client.get_components(rio.SimpleListItem) if li.text == 'G')
            await test_client.execute_js(f'''document.querySelector('[dbg-id="{list_item_id}"]').querySelector('.rio-selectable-item').click()''')
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

            searchable_list = ce.searchable_list
            test_client.get_component(DynamicComponent).session[UserSessionContext].interactive = None

        wr = weakref.ref(ce)
        del ce
        gc.collect()
        assert wr() is not None, 'select_hook must keep CollectionEditor reachable via the widget tree'

        searchable_list.release()
        if widget is not None:
            widget.component = None
            widget.subcomponent = None
        widget = None
        del searchable_list
