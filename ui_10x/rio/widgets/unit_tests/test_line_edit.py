import asyncio

import pytest
import rio.testing
from ui_10x import platform_interface as i
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import LineEdit


@pytest.mark.async_timeout(10)
async def test_line_edit_comprehensive() -> None:
    """Test LineEdit with comprehensive client-widget interaction verification."""
    widget = LineEdit('Initial Text')
    find_input = 'document.querySelector(".rio-input-box").querySelector("input")'
    find_tool_tip = 'document.querySelector(".rio-tooltip-popup").querySelector(".rio-text").children[0].innerText'

    edited_calls = []
    finished_calls = []

    def edited_handler(text):
        edited_calls.append(text)

    def finished_handler():
        finished_calls.append(True)

    widget.text_edited_connect(edited_handler)
    widget.editing_finished_connect(finished_handler)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # 1) Verify client shows widget value
        assert widget.text() == 'Initial Text'
        assert widget.text() == await test_client.execute_js(find_input + '.value')

        # 2) Modify client value (user typing)
        await test_client.execute_js(find_input + '.focus();')
        await test_client.execute_js(find_input + '.value = "User Typed Text";')
        await test_client.execute_js(find_input + '.dispatchEvent(new Event("input"));')
        await asyncio.sleep(1)  # wait for change delay

        # 3) Verify widget reflects client value
        assert widget.text() == 'User Typed Text'
        assert widget.text() == await test_client.execute_js(find_input + '.value')
        assert len(edited_calls) == 1
        assert widget.text() == edited_calls[0]

        # Test editing finished
        await test_client.execute_js(find_input + '.blur();')
        assert len(finished_calls) == 1
        assert widget.text() == await test_client.execute_js(find_input + '.value')

        # Test widget changes propagate to client with timeout protection
        widget.set_text('Widget Updated')
        await test_client.wait_for_refresh()
        client_value = await test_client.execute_js(find_input + '.value')
        assert client_value == 'Widget Updated'
        assert widget.text() == 'Widget Updated'

        # Test tooltip functionality
        widget.set_tool_tip('Helpful tip')
        await test_client.wait_for_refresh()
        await test_client._page.mouse.move(1, 1)
        tooltip_text = await test_client.execute_js(find_tool_tip)
        assert tooltip_text == 'Helpful tip'

        # Test password mode with timeout protection
        assert 'password' != await test_client.execute_js(find_input + '.type')
        widget.set_password_mode()
        await test_client.wait_for_refresh()
        assert 'password' == await test_client.execute_js(find_input + '.type')


async def test_line_edit_disabled_interaction() -> None:
    """Test LineEdit disabled state blocks user interaction."""

    right_button_presses = []
    left_button_presses = []
    class MyLineEdit(LineEdit):
        def mouse_press_event(self, event: i.MouseEvent):
            if event.is_right_button():
                right_button_presses.append(event)
            else:
                left_button_presses.append(event)

    widget = MyLineEdit('Initial Text')
    find_input = 'document.querySelector(".rio-input-box input")'

    edited_calls = []

    def edited_handler(text):
        edited_calls.append(text)

    widget.text_edited_connect(edited_handler)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial enabled state - typing should work
        await test_client.click(10,20, button='right') # handler
        await test_client.click(10,20) # selection
        await test_client._page.press(".rio-input-box input",'A')
        await asyncio.sleep(1)
        assert len(right_button_presses) == 1
        assert len(left_button_presses) == 1
        assert len(edited_calls) == 1
        assert edited_calls[0] == 'A'
        assert widget.text() == 'A'

        # Disable widget
        widget.set_enabled(False)
        await test_client.wait_for_refresh()

        # Verify client shows disabled state
        client_disabled = await test_client.execute_js(find_input + '.disabled')
        assert client_disabled is True

        # Test that typing is blocked when disabled
        await test_client.execute_js(find_input + '.click();')
        await test_client.execute_js(find_input + '.value = "Blocked Text";')
        await test_client.execute_js(find_input + '.blur();')

        await asyncio.sleep(1)
        assert len(edited_calls) == 1  # No additional calls
        assert len(left_button_presses) == 1


        # Re-enable widget
        widget.set_enabled(True)
        await test_client.wait_for_refresh()

        # Verify client shows enabled state
        client_disabled = await test_client.execute_js(find_input + '.disabled')
        assert client_disabled is False

        # Test that typing works again
        await test_client.execute_js(find_input + '.value = "Re-enabled Text";')
        await test_client.execute_js(find_input + '.dispatchEvent(new Event("input"));')
        await asyncio.sleep(1)
        assert len(edited_calls) == initial_calls + 1
        assert edited_calls[-1] == 'Re-enabled Text'
