import asyncio

import rio.testing.browser_client
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import PushButton


async def test_button_comprehensive() -> None:
    """Test PushButton with comprehensive client-widget interaction verification."""
    widget = PushButton('Click Me')
    find_button_text = 'document.querySelector(".rio-button .rio-text").children[0].innerText'

    clicked_calls = []

    def clicked_handler():
        clicked_calls.append(True)

    widget.clicked_connect(clicked_handler)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # 1) Verify client shows widget value
        assert widget['content'] == 'Click Me'
        client_text = await test_client.execute_js(find_button_text)
        assert client_text == 'Click Me'

        # 2) Modify client value (user clicking button)
        await test_client.click(10, 10)  # Click on the button

        # 3) Verify widget reflects client value (click handler called)
        assert len(clicked_calls) == 1
        assert clicked_calls[0] is True

        # Test another click
        await test_client.click(10, 10)
        assert len(clicked_calls) == 2


async def test_button_disabled_interaction() -> None:
    """Test PushButton disabled state blocks user interaction."""
    widget = PushButton('Test Button')

    clicked_calls = []

    def clicked_handler():
        clicked_calls.append(True)

    widget.clicked_connect(clicked_handler)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial enabled state - clicks should work
        await test_client.click(10, 10)
        assert len(clicked_calls) == 1

        # Disable widget
        widget.set_enabled(False)
        await test_client.wait_for_refresh()
        assert not widget['is_sensitive']

        # Test that clicks are blocked when disabled
        await test_client.click(10, 10)
        assert len(clicked_calls) == 1  # No additional calls

        # Re-enable widget
        widget.set_enabled(True)
        await test_client.wait_for_refresh()
        assert widget['is_sensitive']

        # Test that clicks work again
        await test_client.click(10, 10)
        assert len(clicked_calls) == 2


async def test_button_basic_functionality() -> None:
    """Test PushButton basic functionality."""
    widget = PushButton('Test Button')

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial state
        assert widget['content'] == 'Test Button'
        assert widget['is_sensitive']

        # Test enabled/disabled state with timeout protection
        widget.set_enabled(False)
        await test_client.wait_for_refresh()
        assert not widget['is_sensitive']

        widget.set_enabled(True)
        await test_client.wait_for_refresh()
        assert widget['is_sensitive']

        # Test flat style changes with timeout protection
        assert not await test_client.execute_js('document.querySelector(".rio-buttonstyle-plain-text")')
        widget.set_flat(True)
        await test_client.wait_for_refresh()
        assert await test_client.execute_js('document.querySelector(".rio-buttonstyle-plain-text")')
