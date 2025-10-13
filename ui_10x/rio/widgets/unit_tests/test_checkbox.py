import asyncio

import rio.testing
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import CheckBox


async def test_checkbox_comprehensive() -> None:
    """Test CheckBox with comprehensive client-widget interaction verification."""
    widget = CheckBox('Check me')
    find_checkbox = 'document.querySelector("input[type=\'checkbox\']")'

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # 1) Verify client shows widget value (unchecked initially)
        assert not widget.is_checked()
        client_checked = await test_client.execute_js(find_checkbox + '.checked')
        assert client_checked is False

        # 2) Modify client value (user clicking checkbox)
        await test_client.execute_js(find_checkbox + '.click();')
        await asyncio.sleep(0.5)  # Wait for event processing

        # 3) Verify widget reflects client value
        assert widget.is_checked()
        client_checked = await test_client.execute_js(find_checkbox + '.checked')
        assert client_checked is True

        # Test widget changes propagate to client
        widget.set_checked(False)
        await test_client.wait_for_refresh()
        client_checked = await test_client.execute_js(find_checkbox + '.checked')
        assert client_checked is False
        assert not widget.is_checked()

        # Test another client interaction
        await test_client.execute_js(find_checkbox + '.click();')
        await asyncio.sleep(0.5)
        assert widget.is_checked()


async def test_checkbox_disabled_interaction() -> None:
    """Test CheckBox disabled state blocks user interaction."""
    widget = CheckBox('Test Checkbox')
    find_checkbox = 'document.querySelector("input[type=\'checkbox\']")'

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial enabled state - clicks should work
        await test_client.execute_js(find_checkbox + '.click();')
        await asyncio.sleep(0.5)
        assert widget.is_checked()

        # Disable widget
        widget.set_enabled(False)
        await test_client.wait_for_refresh()

        # Verify client shows disabled state
        client_disabled = await test_client.execute_js(find_checkbox + '.disabled')
        assert client_disabled is True

        # Test that clicks are blocked when disabled
        initial_checked = widget.is_checked()
        await test_client.execute_js(find_checkbox + '.click();')
        await asyncio.sleep(0.5)
        assert widget.is_checked() == initial_checked  # State should not change

        # Re-enable widget
        widget.set_enabled(True)
        await test_client.wait_for_refresh()

        # Verify client shows enabled state
        client_disabled = await test_client.execute_js(find_checkbox + '.disabled')
        assert client_disabled is False

        # Test that clicks work again
        await test_client.execute_js(find_checkbox + '.click();')
        await asyncio.sleep(0.5)
        assert not widget.is_checked()  # Should toggle


async def test_checkbox_basic_functionality() -> None:
    """Test CheckBox basic functionality without client interaction."""
    widget = CheckBox('Test Checkbox')

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial state
        assert not widget.is_checked()

        # Test checking
        widget.set_checked(True)
        await test_client.wait_for_refresh()
        assert widget.is_checked()

        # Test unchecking
        widget.set_checked(False)
        await test_client.wait_for_refresh()
        assert not widget.is_checked()

        # Test enabled/disabled state
        widget.set_enabled(False)
        await test_client.wait_for_refresh()

        widget.set_enabled(True)
        await test_client.wait_for_refresh()
