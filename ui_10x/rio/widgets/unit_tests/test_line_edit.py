import asyncio

import pytest
import rio.testing
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import LineEdit


async def test_line_edit() -> None:
    widget = LineEdit('Hello')
    find_edited_text = 'document.querySelector(".rio-input-box").querySelector("input")'
    find_tool_tip = 'document.querySelector(".rio-tooltip-popup").querySelector(".rio-text").children[0].innerText'

    def build() -> rio.Component:
        return DynamicComponent(widget)

    async with rio.testing.BrowserClient(build) as test_client:
        await asyncio.sleep(0.5)
        component = test_client.get_component(rio.TextInput)
        with pytest.raises(ValueError):
            test_client.get_component(rio.Tooltip)

        assert component.text == 'Hello'
        assert 'Hello' == await test_client.execute_js(find_edited_text + '.value')
        await test_client.execute_js(find_edited_text + '.focus();')
        await test_client.execute_js(find_edited_text + '.value = "Goodbye";')
        await test_client.execute_js(find_edited_text + '.blur();')
        assert component.text == 'Goodbye'
        assert widget.text() == 'Goodbye'

        widget.set_text('Done')
        await test_client.wait_for_refresh()
        assert 'Done' == await test_client.execute_js(find_edited_text + '.value')
        assert component.text == 'Done'
        assert widget.text() == 'Done'

        widget.set_tool_tip('Tip')
        await test_client.wait_for_refresh()
        assert 'Done' == await test_client.execute_js(find_edited_text + '.value')
        assert component.text == 'Done'
        assert widget.text() == 'Done'
        await test_client._page.mouse.move(1, 1)
        assert 'Tip' == await test_client.execute_js(find_tool_tip)
