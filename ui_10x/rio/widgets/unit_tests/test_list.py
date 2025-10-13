import asyncio

import rio.testing.browser_client
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import ListWidget


async def test_list_comprehensive() -> None:
    """Test ListWidget with comprehensive client-widget interaction verification."""
    widget = ListWidget()
    widget.add_items(['Item 1', 'Item 2', 'Item 3'])

    find_list_items = 'document.querySelectorAll(".rio-selectable-item")'
    find_selected_text = 'document.querySelector(".selected").querySelector(".rio-text").children[0].innerText'

    clicked_calls = []

    def clicked_handler(item):
        clicked_calls.append(item)

    widget.clicked_connect(clicked_handler)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # 1) Verify client shows widget value (list items)
        assert widget.child_count() == 3
        client_items = await test_client.execute_js(f'{find_list_items}.length')
        assert client_items == 3

        # 2) Modify client value (user clicking first item)
        await test_client.click(10, 1)
        await asyncio.sleep(0.5)

        # 3) Verify widget reflects client value
        assert len(clicked_calls) == 1
        assert clicked_calls[0]['text'] == 'Item 1'
        assert widget['selected_items'] == [clicked_calls[0]['key']]

        # Verify client shows selection
        selected_text = await test_client.execute_js(find_selected_text)
        assert selected_text == 'Item 1'

        # Test clicking second item
        await test_client.click(10, test_client.window_height_in_pixels - 1)
        await asyncio.sleep(0.5)
        assert len(clicked_calls) == 2
        assert clicked_calls[1]['text'] == 'Item 3'  # Last item
        assert widget['selected_items'] == [clicked_calls[1]['key']]

        # Test widget changes propagate to client (clearing list)
        widget.clear()
        assert not widget.get_children()
        await test_client.wait_for_refresh()
        assert not widget.subcomponent.selected_items
        client_items = await test_client.execute_js(f'{find_list_items}.length')
        assert client_items == 0

        # Test adding item
        widget.add_item('New Item')
        await test_client.wait_for_refresh()
        assert widget.child_count() == 1
        client_items = await test_client.execute_js(f'{find_list_items}.length')
        assert client_items == 1

        # Test clicking new item
        await test_client.click(10, 1)
        await asyncio.sleep(0.5)
        assert len(clicked_calls) == 3
        assert clicked_calls[2]['text'] == 'New Item'


async def test_list_item_management() -> None:
    """Test ListWidget item management operations."""
    widget = ListWidget()
    widget.add_items(['A', 'B', 'C'])

    find_list_items = 'document.querySelectorAll(".rio-selectable-item")'

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial state
        assert widget.child_count() == 3
        client_items = await test_client.execute_js(f'{find_list_items}.length')
        assert client_items == 3

        # Test removing item
        removed_item = widget.take_item(1)  # Remove 'B'
        await test_client.wait_for_refresh()
        assert widget.child_count() == 2
        client_items = await test_client.execute_js(f'{find_list_items}.length')
        assert client_items == 2
        assert removed_item['text'] == 'B'

        # Test adding another item with timeout protection
        widget.add_item('Inserted')
        await test_client.wait_for_refresh()
        assert widget.child_count() == 3
        client_items = await test_client.execute_js(f'{find_list_items}.length')
        assert client_items == 3


async def test_list_disabled_interaction() -> None:
    """Test ListWidget disabled state blocks user interaction."""
    widget = ListWidget()
    widget.add_items(['Item 1', 'Item 2', 'Item 3'])

    clicked_calls = []

    def clicked_handler(item):
        clicked_calls.append(item)

    widget.clicked_connect(clicked_handler)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial enabled state - clicks should work
        await test_client.click(10, 1)
        await asyncio.sleep(0.5)
        assert len(clicked_calls) == 1
        assert clicked_calls[0]['text'] == 'Item 1'
        assert widget['selected_items'] == [id(widget.get_children()[0])]

        # Disable widget
        widget.set_enabled(False)
        await test_client.wait_for_refresh()

        # Test that clicks are blocked when disabled
        initial_calls = len(clicked_calls)
        await test_client.click(10, 1)
        await asyncio.sleep(0.5)
        assert len(clicked_calls) == initial_calls  # No additional calls
        assert widget['selected_items'] == [id(widget.get_children()[0])]

        # Re-enable widget
        widget.set_enabled(True)
        await test_client.wait_for_refresh()

        # Test that clicks work again
        await test_client.click(10, 1)
        await asyncio.sleep(0.5)
        assert len(clicked_calls) == initial_calls + 1
        assert clicked_calls[-1]['text'] == 'Item 1'
        assert widget['selected_items'] == []
