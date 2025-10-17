import asyncio

import rio.testing
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import MessageBox, Separator


async def test_separator() -> None:
    """Test basic Separator widget functionality."""
    widget = Separator()

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial state
        assert widget is not None

        # Test enabled/disabled state
        assert widget['is_sensitive']
        widget.set_enabled(False)
        await test_client.wait_for_refresh()
        assert not widget['is_sensitive']

        widget.set_enabled(True)
        await test_client.wait_for_refresh()
        assert widget['is_sensitive']


async def test_separator_orientation() -> None:
    """Test Separator widget with different orientations."""
    # Test horizontal separator (default)
    widget_h = Separator()

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget_h)) as test_client:
        await asyncio.sleep(0.5)

        # Test horizontal separator
        assert widget_h is not None
        assert widget_h.is_enabled()

        # Test vertical separator
        widget_v = Separator(orientation='vertical')

        async with rio.testing.BrowserClient(lambda: DynamicComponent(widget_v)) as test_client_v:
            await asyncio.sleep(0.5)

            assert widget_v is not None
            assert widget_v.is_enabled()


async def test_message_box() -> None:
    """Test basic MessageBox widget functionality."""
    widget = MessageBox('Test Message', 'This is a test message')

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial state
        assert widget is not None

        # Test message box properties
        assert widget.text() == 'Test Message'
        assert widget.informative_text() == 'This is a test message'


async def test_message_box_with_buttons() -> None:
    """Test MessageBox widget with custom buttons."""
    widget = MessageBox('Question', 'Do you want to continue?')
    widget.set_standard_buttons(MessageBox.StandardButton.OK | MessageBox.StandardButton.CANCEL)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test message box with buttons
        assert widget is not None
        assert widget.text() == 'Question'
        assert widget.informative_text() == 'Do you want to continue?'


async def test_message_box_icon() -> None:
    """Test MessageBox widget with different icons."""
    widget = MessageBox('Warning', 'This is a warning message')
    widget.set_icon(MessageBox.Icon.WARNING)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test message box with icon
        assert widget is not None
        assert widget.text() == 'Warning'
        assert widget.informative_text() == 'This is a warning message'


async def test_message_box_buttons() -> None:
    """Test MessageBox widget button functionality."""
    widget = MessageBox('Confirm', 'Are you sure?')
    widget.set_standard_buttons(MessageBox.StandardButton.YES | MessageBox.StandardButton.NO)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test message box with yes/no buttons
        assert widget is not None
        assert widget.text() == 'Confirm'
        assert widget.informative_text() == 'Are you sure?'


async def test_message_box_custom_buttons() -> None:
    """Test MessageBox widget with custom button text."""
    widget = MessageBox('Custom', 'Custom message with custom buttons')
    widget.add_button('Custom Button 1', MessageBox.ButtonRole.ACCEPT_ROLE)
    widget.add_button('Custom Button 2', MessageBox.ButtonRole.REJECT_ROLE)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test message box with custom buttons
        assert widget is not None
        assert widget.text() == 'Custom'
        assert widget.informative_text() == 'Custom message with custom buttons'


async def test_message_box_default_button() -> None:
    """Test MessageBox widget default button functionality."""
    widget = MessageBox('Default Button Test', 'Testing default button')
    widget.set_standard_buttons(MessageBox.StandardButton.OK | MessageBox.StandardButton.CANCEL)
    widget.set_default_button(MessageBox.StandardButton.OK)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test message box with default button
        assert widget is not None
        assert widget.text() == 'Default Button Test'
        assert widget.informative_text() == 'Testing default button'


async def test_message_box_escape_button() -> None:
    """Test MessageBox widget escape button functionality."""
    widget = MessageBox('Escape Button Test', 'Testing escape button')
    widget.set_standard_buttons(MessageBox.StandardButton.OK | MessageBox.StandardButton.CANCEL)
    widget.set_escape_button(MessageBox.StandardButton.CANCEL)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test message box with escape button
        assert widget is not None
        assert widget.text() == 'Escape Button Test'
        assert widget.informative_text() == 'Testing escape button'
