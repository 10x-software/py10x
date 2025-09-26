import asyncio
from unittest.mock import MagicMock

import rio.testing.browser_client
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import PushButton

rio.testing.browser_client.DEBUGGER_ACTIVE = False # this is triggered by a) debugger or b) coverage. TODO: can we tell a) from b)?

#@pytest.mark.async_timeout(20)
async def test_handler() -> None:
    widget = PushButton('Hello')
    handler = MagicMock()
    widget.clicked_connect(handler)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(1)
        center_x = test_client.window_width_in_pixels * 0.5
        center_y = test_client.window_height_in_pixels * 0.5
        await test_client.click(center_x, center_y)

        assert handler.called


async def test_button() -> None:
    widget = PushButton('Hello')

    async with rio.testing.DummyClient(lambda: DynamicComponent(widget)) as test_client:
        text_component = test_client.get_component(rio.Text)
        assert text_component.text == 'Hello'
        widget.set_text('Done')
        await test_client.wait_for_refresh()
        assert text_component.text == 'Done'
