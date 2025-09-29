import asyncio
from unittest.mock import MagicMock

import rio.testing.browser_client
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import ListWidget


async def test_list() -> None:
    widget = ListWidget()
    widget.add_items('A B'.split())
    handler = MagicMock()
    widget.clicked_connect(handler)
    find_selected_text = 'document.querySelector(".selected").querySelector(".rio-text").children[0].innerText;'

    def check_item(expected_text,selected_text):
        assert expected_text == selected_text
        item = handler.call_args.args[0]
        assert expected_text == item['text']
        assert widget['selected_items'] == [item['key']]
        return item

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(1)
        items = []

        await test_client.click(10, 1)
        assert handler.call_count == 1
        items.append(check_item('A',await test_client.execute_js(find_selected_text)))

        await test_client.click(10, test_client.window_height_in_pixels - 1)
        assert handler.call_count == 2
        items.append(check_item('B',await test_client.execute_js(find_selected_text)))

        assert widget.get_children() == items

        widget.clear()
        assert not widget.get_children()
        await test_client.wait_for_refresh()
        assert not widget.subcomponent.selected_items

        widget.add_item('C')
        await test_client.wait_for_refresh()
        assert widget.child_count() == 1

        await test_client.click(10, 1)
        assert handler.call_count == 3
        item = check_item('C',await test_client.execute_js(find_selected_text))

        assert item == widget.take_item(0)
        assert not widget.get_children()
        await test_client.wait_for_refresh()
        assert not widget.subcomponent.selected_items


