import asyncio
from datetime import date

import pytest
import rio.testing.browser_client
from core_10x.code_samples.person import Person
from core_10x.exec_control import CACHE_ONLY, INTERACTIVE
from ui_10x.collection_editor import Collection, CollectionEditor
from ui_10x.rio.component_builder import DynamicComponent


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
        await asyncio.sleep(0.5)

        assert await test_client.execute_js('document.querySelector(".rio-selectable-item").innerText') == 'Ilya|Pevzner'
        await test_client.execute_js('document.querySelector(".rio-selectable-item").click()')
        await asyncio.sleep(0.5)

        assert await test_client.execute_js('document.querySelectorAll("input")[8].value') == 'LB'
        assert await test_client.execute_js('document.querySelectorAll("input")[7].value') == '200.00'

        button_id = next(b._id_ for b in test_client.get_components(rio.Button) if b.content == 'edit')
        await test_client.execute_js(f'''document.querySelector('[dbg-id="{button_id}"]').querySelector('rio-pressable-element').click()''')
        await asyncio.sleep(0.5)

        assert await test_client.execute_js('document.querySelectorAll("input")[16].value') == 'LB'
        assert await test_client.execute_js('document.querySelectorAll("input")[15].value') == '200.00'

        button_id = next(b._id_ for b in test_client.get_components(rio.Button) if b.icon == 'material/arrow_downward')
        await test_client.execute_js(f'''document.querySelector('[dbg-id="{button_id}"]').querySelector('rio-pressable-element').click()''')
        await asyncio.sleep(0.5)

        print([li.text for li in test_client.get_components(rio.SimpleListItem)])
        list_item_id = next(li._id_ for li in test_client.get_components(rio.SimpleListItem) if li.text == 'G')
        await test_client.execute_js(f'''document.querySelector('[dbg-id="{list_item_id}"]').querySelector('.rio-selectable-item').click()''')

        assert await test_client.execute_js('document.querySelectorAll("input")[16].value') == 'G'
        assert await test_client.execute_js('document.querySelectorAll("input")[15].value') == '90,702.95'

        button_id = next(b._id_ for b in test_client.get_components(rio.Button) if b.content == 'Ok')
        await test_client.execute_js(f'''document.querySelector('[dbg-id="{button_id}"]').querySelector('rio-pressable-element').click()''')
        await asyncio.sleep(0.5)

        assert await test_client.execute_js('document.querySelectorAll("input")[8].value') == 'G'
        assert await test_client.execute_js('document.querySelectorAll("input")[7].value') == '90,702.95'
