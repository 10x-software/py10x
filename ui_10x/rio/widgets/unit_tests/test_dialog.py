import asyncio

import rio.testing
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import Dialog, Label, PushButton, VBoxLayout


async def test_dialog() -> None:
    """Test basic Dialog widget functionality."""
    widget = Dialog(title='Test Dialog')

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial state
        assert widget is not None
        assert widget.title == 'Test Dialog'

        # Test enabled/disabled state
        assert widget['is_sensitive']
        widget.set_enabled(False)
        await test_client.wait_for_refresh()
        assert not widget['is_sensitive']

        widget.set_enabled(True)
        await test_client.wait_for_refresh()
        assert widget['is_sensitive']


async def test_dialog_with_children() -> None:
    """Test Dialog widget with child widgets."""
    label = Label('Dialog Content')
    button = PushButton('OK')

    widget = Dialog(title='Dialog with Children', children=[label, button])

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test title
        assert widget.title == 'Dialog with Children'

        # Test children
        children = widget.get_children()
        assert len(children) == 2
        assert label in children
        assert button in children


async def test_dialog_title_change() -> None:
    """Test Dialog widget title change functionality."""
    widget = Dialog(title='Initial Title')

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial title
        assert widget.title == 'Initial Title'

        # Test title change
        widget.set_window_title('Updated Title')
        await test_client.wait_for_refresh()
        assert widget.title == 'Updated Title'


async def test_dialog_accept_reject() -> None:
    """Test Dialog widget accept/reject functionality."""
    accept_calls = []
    reject_calls = []

    def on_accept():
        accept_calls.append(True)

    def on_reject():
        reject_calls.append(True)

    widget = Dialog(title='Accept/Reject Test', on_accept=on_accept, on_reject=on_reject)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial state
        assert widget.accepted is True  # Default value

        # Test accept
        widget.done(1)  # Accept
        assert widget.accepted is True

        # Test reject
        widget.reject()
        assert widget.accepted is False


async def test_dialog_modal() -> None:
    """Test Dialog widget modal functionality."""
    widget = Dialog(title='Modal Dialog')

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial modal state
        assert widget._modal is True  # Default modal state

        # Test that dialog is functional
        assert widget['is_sensitive']


async def test_dialog_with_layout() -> None:
    """Test Dialog widget with layout content."""
    layout = VBoxLayout()
    label1 = Label('First Label')
    label2 = Label('Second Label')
    button = PushButton('Close')

    layout.add_widget(label1)
    layout.add_widget(label2)
    layout.add_widget(button)

    widget = Dialog(title='Dialog with Layout', children=[layout])

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test title
        assert widget.title == 'Dialog with Layout'

        # Test layout is added
        children = widget.get_children()
        assert len(children) == 1
        assert layout in children

        # Test layout children
        layout_children = layout.get_children()
        assert len(layout_children) == 3
        assert label1 in layout_children
        assert label2 in layout_children
        assert button in layout_children


async def test_dialog_result() -> None:
    """Test Dialog widget result functionality."""
    widget = Dialog(title='Result Test')

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial result state
        assert widget.accepted is True

        # Test done with different results
        widget.done(1)  # Accept
        assert widget.accepted is True

        widget.done(0)  # Reject
        assert widget.accepted is False


async def test_dialog_callback_wrappers() -> None:
    """Test Dialog widget callback wrapper functionality."""
    accept_calls = []
    reject_calls = []

    def accept_callback():
        accept_calls.append('accept')

    def reject_callback():
        reject_calls.append('reject')

    widget = Dialog(title='Callback Test', on_accept=accept_callback, on_reject=reject_callback)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test that callbacks are set
        assert widget.on_accept is not None
        assert widget.on_reject is not None

        # Test callback execution
        widget.on_accept()
        assert len(accept_calls) == 1
        assert accept_calls[0] == 'accept'

        widget.on_reject()
        assert len(reject_calls) == 1
        assert reject_calls[0] == 'reject'


async def test_dialog_no_callbacks() -> None:
    """Test Dialog widget without callbacks."""
    widget = Dialog(title='No Callbacks')

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test that dialog works without callbacks
        assert widget.title == 'No Callbacks'
        assert widget['is_sensitive']

        # Test that accept/reject still work
        widget.done(1)
        assert widget.accepted is True

        widget.reject()
        assert widget.accepted is False


async def test_dialog_size_policy() -> None:
    """Test Dialog widget size policy."""
    widget = Dialog(title='Size Test')

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test setting minimum size
        widget.set_minimum_width(300)
        widget.set_minimum_height(200)
        await test_client.wait_for_refresh()

        # Test that dialog is still functional
        assert widget['is_sensitive']
        assert widget.title == 'Size Test'


async def test_dialog_client_interaction() -> None:
    """Test Dialog widget client interaction with timeout protection."""
    widget = Dialog(title='Client Test')
    label = Label('Dialog Content')
    widget.add_widget(label)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial state
        assert widget.title == 'Client Test'
        assert len(widget.get_children()) == 1

        # Test widget property changes
        widget.set_window_title('Updated Title')
        await test_client.wait_for_refresh()
        assert widget.title == 'Updated Title'

        # Verify client state reflects widget changes
        client_ready = await test_client.execute_js('document.querySelector(".rio-dialog") !== null')
        assert client_ready is True
        assert widget.title == 'Updated Title'
