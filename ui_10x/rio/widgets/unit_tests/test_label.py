import asyncio

import rio.testing.browser_client
from ui_10x.rio.browser_helpers import wait_for_js_truthy, wait_for_label_client_text
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import Label


async def check_text(widget, test_client, text):
    assert widget['text'] == text
    await wait_for_label_client_text(test_client, text)


async def test_label() -> None:
    """Test basic Label widget functionality with client interaction verification."""
    widget = Label('Hello World')

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        assert widget['text'] == 'Hello World'

        widget.set_text('Updated Text')
        await test_client.wait_for_refresh()
        await check_text(widget, test_client, 'Updated Text')


async def test_label_empty() -> None:
    """Test Label widget with empty text and client validation."""
    widget = Label()

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        await check_text(widget, test_client, '')

        widget.set_text('New Text')
        await test_client.wait_for_refresh()
        await check_text(widget, test_client, 'New Text')
