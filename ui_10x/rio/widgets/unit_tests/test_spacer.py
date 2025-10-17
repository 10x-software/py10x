import asyncio

import rio.testing
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import Spacer


async def test_spacer() -> None:
    """Test basic Spacer widget functionality."""
    widget = Spacer()

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test that spacer is created successfully
        assert widget is not None

        # Test that spacer can be enabled/disabled
        assert widget['is_sensitive']
        widget.set_enabled(False)
        await test_client.wait_for_refresh()
        assert not widget['is_sensitive']

        widget.set_enabled(True)
        await test_client.wait_for_refresh()
        assert widget['is_sensitive']


async def test_spacer_with_size() -> None:
    """Test Spacer widget with specific size parameters."""
    # Test spacer with width and height
    widget = Spacer()

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial state
        assert widget is not None

        # Test setting minimum size
        widget.set_minimum_width(50)
        widget.set_minimum_height(30)
        await test_client.wait_for_refresh()

        # Verify the spacer is still functional
        assert widget['is_sensitive']


async def test_spacer_in_layout() -> None:
    """Test Spacer widget behavior in a layout context."""
    from ui_10x.rio.widgets import Label, VBoxLayout

    layout = VBoxLayout()
    label1 = Label('Top')
    label2 = Label('Bottom')
    spacer = Spacer()

    layout.add_widget(label1)
    layout.add_widget(spacer)
    layout.add_widget(label2)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(layout)) as test_client:
        await asyncio.sleep(0.5)

        # Test that spacer is part of the layout
        assert spacer in layout.get_children()

        # Test spacer functionality within layout
        assert spacer.is_enabled()

        # Test spacer can be removed from layout
        layout.remove_widget(spacer)
        await test_client.wait_for_refresh()
        assert spacer not in layout.get_children()
