import asyncio

import rio.testing
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import TextEdit

find_textarea = 'document.querySelector("textarea")'


async def test_text_edit() -> None:
    """Test basic TextEdit widget functionality with client-widget interaction verification."""
    widget = TextEdit('Initial text')

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial text - verify both widget and client
        assert widget.to_plain_text() == 'Initial text'
        client_text = await test_client.execute_js(find_textarea + '.value')
        assert client_text == 'Initial text'

        # Test text change - verify widget update propagates to client
        widget.set_plain_text('Updated text')
        await test_client.wait_for_refresh()
        assert widget.to_plain_text() == 'Updated text'
        client_text = await test_client.execute_js(find_textarea + '.value')
        assert client_text == 'Updated text'


async def test_text_edit_interactions() -> None:
    """Test TextEdit widget read-only functionality."""

    focus_out = []

    class MyTextEdit(TextEdit):
        def focus_out_event(self, event):
            focus_out.append(self['text'])

    widget = MyTextEdit()

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial state
        assert widget['is_sensitive']
        assert widget.to_plain_text() == ''
        assert widget.to_plain_text() == await test_client.execute_js(find_textarea + '.value')

        await test_client.execute_js(find_textarea + '.focus()')
        await test_client.execute_js(find_textarea + '.value="Read-only text"')
        await test_client.execute_js(find_textarea + '.blur()')
        await asyncio.sleep(0.5)
        assert widget.to_plain_text() == 'Read-only text'
        assert focus_out == [widget.to_plain_text()]

        # Test setting read-only
        widget.set_read_only(True)
        assert not widget['is_sensitive']
        await test_client.wait_for_refresh()
        await test_client.execute_js(find_textarea + '.focus()')
        await test_client.execute_js(find_textarea + '.value="Read-only text - modified"')
        await test_client.execute_js(find_textarea + '.blur()')
        await asyncio.sleep(0.5)
        assert widget.to_plain_text() == 'Read-only text'
        assert focus_out == [widget.to_plain_text()]

        # Test unsetting read-only
        widget.set_read_only(False)
        assert widget['is_sensitive']
        await test_client.wait_for_refresh()
        await test_client.execute_js(find_textarea + '.focus()')
        await test_client.execute_js(find_textarea + '.value="Modified text"')
        await test_client.execute_js(find_textarea + '.blur()')
        await asyncio.sleep(0.5)
        assert widget.to_plain_text() == 'Modified text'
        assert len(focus_out) == 2
        assert focus_out[-1] == widget.to_plain_text()


#TODO: test clipboard interactions
# async def test_text_edit_selection() -> None:
#     """Test TextEdit widget text selection functionality."""
#     widget = TextEdit('Selectable text content')
#
#     async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
#         await asyncio.sleep(0.5)
#
#         # Test initial state
#         assert widget.to_plain_text() == 'Selectable text content'
#
#         # Test select all
#         widget.select_all()
#         await test_client.wait_for_refresh()
#
#         # Test copy (if supported)
#         # Note: Copy functionality might not be testable in browser client
#         # but we can test that the selection methods don't raise errors
#         widget.copy()
#         await test_client.wait_for_refresh()


async def test_text_edit_enabled_disabled() -> None:
    """Test TextEdit widget enabled/disabled state."""
    widget = TextEdit('Test text')

    async with rio.testing.DummyClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial enabled state
        assert widget['is_sensitive']

        # Test disabling
        widget.set_enabled(False)
        await test_client.wait_for_refresh()
        assert not widget['is_sensitive']

        # Test re-enabling
        widget.set_enabled(True)
        await test_client.wait_for_refresh()
        assert widget['is_sensitive']
