import asyncio

import rio.testing
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import Direction, Label, Splitter


async def test_splitter() -> None:
    """Test basic Splitter widget functionality."""
    widget = Splitter()

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


async def test_splitter_with_children() -> None:
    """Test Splitter widget with child widgets."""
    label1 = Label('Left/Top')
    label2 = Label('Right/Bottom')

    widget = Splitter(label1, label2)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test children
        children = widget.get_children()
        assert len(children) == 2
        assert label1 in children
        assert label2 in children


async def test_splitter_horizontal() -> None:
    """Test Splitter widget with horizontal orientation."""
    label1 = Label('Left')
    label2 = Label('Right')

    widget = Splitter(label1, label2, orientation=Direction.HORIZONTAL)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test children
        children = widget.get_children()
        assert len(children) == 2
        assert label1 in children
        assert label2 in children

        # Test orientation
        assert widget.orientation() == Direction.HORIZONTAL


async def test_splitter_vertical() -> None:
    """Test Splitter widget with vertical orientation."""
    label1 = Label('Top')
    label2 = Label('Bottom')

    widget = Splitter(label1, label2, orientation=Direction.VERTICAL)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test children
        children = widget.get_children()
        assert len(children) == 2
        assert label1 in children
        assert label2 in children

        # Test orientation
        assert widget.orientation() == Direction.VERTICAL


async def test_splitter_add_remove_children() -> None:
    """Test Splitter widget adding and removing children."""
    widget = Splitter()
    label1 = Label('First')
    label2 = Label('Second')
    label3 = Label('Third')

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial empty state
        assert len(widget.get_children()) == 0

        # Test adding children
        widget.add_widget(label1)
        await test_client.wait_for_refresh()
        assert len(widget.get_children()) == 1
        assert label1 in widget.get_children()

        widget.add_widget(label2)
        await test_client.wait_for_refresh()
        assert len(widget.get_children()) == 2
        assert label2 in widget.get_children()

        widget.add_widget(label3)
        await test_client.wait_for_refresh()
        assert len(widget.get_children()) == 3
        assert label3 in widget.get_children()

        # Test removing children
        widget.remove_widget(label2)
        await test_client.wait_for_refresh()
        assert len(widget.get_children()) == 2
        assert label2 not in widget.get_children()
        assert label1 in widget.get_children()
        assert label3 in widget.get_children()


async def test_splitter_orientation_change() -> None:
    """Test Splitter widget orientation change."""
    label1 = Label('First')
    label2 = Label('Second')

    widget = Splitter(label1, label2, orientation=Direction.HORIZONTAL)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial orientation
        assert widget.orientation() == Direction.HORIZONTAL

        # Test changing orientation
        widget.set_orientation(Direction.VERTICAL)
        await test_client.wait_for_refresh()
        assert widget.orientation() == Direction.VERTICAL

        # Test changing back
        widget.set_orientation(Direction.HORIZONTAL)
        await test_client.wait_for_refresh()
        assert widget.orientation() == Direction.HORIZONTAL


async def test_splitter_sizes() -> None:
    """Test Splitter widget size management."""
    label1 = Label('First')
    label2 = Label('Second')

    widget = Splitter(label1, label2)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test setting minimum sizes
        widget.set_minimum_width(200)
        widget.set_minimum_height(150)
        await test_client.wait_for_refresh()

        # Test that splitter is still functional
        assert widget['is_sensitive']
        assert len(widget.get_children()) == 2


async def test_splitter_clear() -> None:
    """Test Splitter widget clear functionality."""
    label1 = Label('First')
    label2 = Label('Second')

    widget = Splitter(label1, label2)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial state
        assert len(widget.get_children()) == 2

        # Test clear
        widget.clear()
        await test_client.wait_for_refresh()
        assert len(widget.get_children()) == 0
