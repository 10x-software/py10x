import asyncio

import rio.testing.browser_client
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import PushButton


async def test_handler() -> None:
    """Test button click handler with client-widget interaction verification."""
    widget = PushButton('Hello')
    handler_calls = []
    find_button_text = 'document.querySelector(".rio-button .rio-text").children[0].innerText'

    def handler():
        handler_calls.append(True)

    widget.clicked_connect(handler)
    check_flat = 'document.querySelector(".rio-buttonstyle-plain-text");'

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial state - verify both widget and client
        assert widget['content'] == 'Hello'
        client_text = await test_client.execute_js(find_button_text)
        assert client_text == 'Hello'

        # Test client interaction - user clicking button
        await test_client.click(10, 10)
        assert len(handler_calls) == 1

        # Test widget property change propagates to client
        assert not await test_client.execute_js(check_flat)
        widget.set_flat(True)
        await test_client.wait_for_refresh()
        assert await test_client.execute_js(check_flat)


async def test_button() -> None:
    hello = 'Hello'
    done = 'Done'
    widget = PushButton('Hello')

    async with rio.testing.DummyClient(lambda: DynamicComponent(widget)) as test_client:
        text_component = test_client.get_component(rio.Text)
        assert text_component.text == hello
        widget.set_text(done)
        await test_client.wait_for_refresh()
        assert text_component.text == done
