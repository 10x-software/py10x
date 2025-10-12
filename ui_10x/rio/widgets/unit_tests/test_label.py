import asyncio

import rio.testing.browser_client
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import Label


async def check_text(widget, test_client, text):
    assert widget['text'] == text
    client_text = await test_client.execute_js('document.querySelector(".rio-text")?.children[0]?.innerText || ""')
    assert client_text == text


async def test_label() -> None:
    """Test basic Label widget functionality with client interaction verification."""
    widget = Label('Hello World')

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial text - verify widget state
        assert widget['text'] == 'Hello World'

        # Test text change - verify widget update
        widget.set_text('Updated Text')
        await test_client.wait_for_refresh()
        await check_text(widget, test_client, 'Updated Text')


async def test_label_empty() -> None:
    """Test Label widget with empty text and client validation."""
    widget = Label()

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test empty text
        await check_text(widget, test_client, '')

        # Test setting text
        widget.set_text('New Text')
        await test_client.wait_for_refresh()
        await check_text(widget, test_client, 'New Text')
