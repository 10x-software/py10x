import asyncio

import rio.testing
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import SCROLL, Label, ScrollArea, VBoxLayout


async def test_scroll_area() -> None:
    """Test basic ScrollArea widget functionality."""
    widget = ScrollArea()

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


async def test_scroll_area_with_content() -> None:
    """Test ScrollArea widget with content."""
    # Create content for the scroll area
    content_layout = VBoxLayout()
    for i in range(10):
        content_layout.add_widget(Label(f'Label {i}'))

    widget = ScrollArea()
    widget.set_widget(content_layout)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test that content is set
        assert widget.widget() == content_layout

        # Test that scroll area is functional
        assert widget['is_sensitive']


async def test_scroll_area_scroll_policy() -> None:
    """Test ScrollArea widget scroll policy settings."""
    widget = ScrollArea()

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial scroll policy
        assert widget.horizontal_scroll_bar_policy() == SCROLL.AS_NEEDED
        assert widget.vertical_scroll_bar_policy() == SCROLL.AS_NEEDED

        # Test setting scroll policies
        widget.set_horizontal_scroll_bar_policy(SCROLL.ALWAYS_ON)
        widget.set_vertical_scroll_bar_policy(SCROLL.ALWAYS_OFF)
        await test_client.wait_for_refresh()

        assert widget.horizontal_scroll_bar_policy() == SCROLL.ALWAYS_ON
        assert widget.vertical_scroll_bar_policy() == SCROLL.ALWAYS_OFF


async def test_scroll_area_widget_management() -> None:
    """Test ScrollArea widget content management."""
    widget = ScrollArea()
    label1 = Label('First label')
    label2 = Label('Second label')

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial empty state
        assert widget.widget() is None

        # Test setting widget
        widget.set_widget(label1)
        await test_client.wait_for_refresh()
        assert widget.widget() == label1

        # Test changing widget
        widget.set_widget(label2)
        await test_client.wait_for_refresh()
        assert widget.widget() == label2

        # Test clearing widget
        widget.set_widget(None)
        await test_client.wait_for_refresh()
        assert widget.widget() is None


async def test_scroll_area_with_layout() -> None:
    """Test ScrollArea widget with layout content."""
    # Create a layout with many items to test scrolling
    content_layout = VBoxLayout()
    for i in range(20):
        content_layout.add_widget(Label(f'Scrollable item {i}'))

    widget = ScrollArea()
    widget.set_widget(content_layout)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test that layout is set as content
        assert widget.widget() == content_layout

        # Test that scroll area is functional with layout
        assert widget['is_sensitive']

        # Test scroll area properties
        assert widget.horizontal_scroll_bar_policy() == SCROLL.AS_NEEDED
        assert widget.vertical_scroll_bar_policy() == SCROLL.AS_NEEDED


async def test_scroll_area_size_policy() -> None:
    """Test ScrollArea widget size policy."""
    widget = ScrollArea()

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test setting minimum size
        widget.set_minimum_width(200)
        widget.set_minimum_height(150)
        await test_client.wait_for_refresh()

        # Test that scroll area is still functional
        assert widget['is_sensitive']

        # Test scroll policies are still accessible
        assert widget.horizontal_scroll_bar_policy() == SCROLL.AS_NEEDED
        assert widget.vertical_scroll_bar_policy() == SCROLL.AS_NEEDED
