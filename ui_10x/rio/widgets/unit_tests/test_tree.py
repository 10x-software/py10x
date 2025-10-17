import asyncio

import rio.testing
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import TreeItem, TreeWidget


async def test_tree_widget() -> None:
    """Test basic TreeWidget functionality."""
    widget = TreeWidget()

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


async def test_tree_widget_with_items() -> None:
    """Test TreeWidget with TreeItem children."""
    widget = TreeWidget()
    item1 = TreeItem('Item 1')
    item2 = TreeItem('Item 2')
    item3 = TreeItem('Item 3')

    widget.add_top_level_item(item1)
    widget.add_top_level_item(item2)
    widget.add_top_level_item(item3)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test top level items
        assert widget.top_level_item_count() == 3
        assert widget.top_level_item(0) == item1
        assert widget.top_level_item(1) == item2
        assert widget.top_level_item(2) == item3


async def test_tree_widget_hierarchical_items() -> None:
    """Test TreeWidget with hierarchical TreeItem structure."""
    widget = TreeWidget()

    # Create parent item
    parent_item = TreeItem('Parent')
    widget.add_top_level_item(parent_item)

    # Create child items
    child1 = TreeItem('Child 1')
    child2 = TreeItem('Child 2')
    parent_item.add_child(child1)
    parent_item.add_child(child2)

    # Create grandchild
    grandchild = TreeItem('Grandchild')
    child1.add_child(grandchild)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test top level items
        assert widget.top_level_item_count() == 1
        assert widget.top_level_item(0) == parent_item

        # Test child items
        assert parent_item.child_count() == 2
        assert parent_item.child(0) == child1
        assert parent_item.child(1) == child2

        # Test grandchild
        assert child1.child_count() == 1
        assert child1.child(0) == grandchild


async def test_tree_widget_item_selection() -> None:
    """Test TreeWidget item selection functionality."""
    widget = TreeWidget()
    item1 = TreeItem('Item 1')
    item2 = TreeItem('Item 2')
    item3 = TreeItem('Item 3')

    widget.add_top_level_item(item1)
    widget.add_top_level_item(item2)
    widget.add_top_level_item(item3)

    selection_changed_calls = []

    def selection_changed_handler():
        selection_changed_calls.append(True)

    widget.item_selection_changed_connect(selection_changed_handler)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial selection
        assert widget.current_item() is None

        # Test setting current item
        widget.set_current_item(item2)
        await test_client.wait_for_refresh()
        assert widget.current_item() == item2

        # Test selecting item
        widget.select_item(item1)
        await test_client.wait_for_refresh()
        assert widget.is_item_selected(item1)
        assert not widget.is_item_selected(item2)
        assert not widget.is_item_selected(item3)


async def test_tree_widget_item_expansion() -> None:
    """Test TreeWidget item expansion/collapse functionality."""
    widget = TreeWidget()
    parent_item = TreeItem('Parent')
    child_item = TreeItem('Child')

    widget.add_top_level_item(parent_item)
    parent_item.add_child(child_item)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial collapsed state
        assert not widget.is_item_expanded(parent_item)

        # Test expanding item
        widget.expand_item(parent_item)
        await test_client.wait_for_refresh()
        assert widget.is_item_expanded(parent_item)

        # Test collapsing item
        widget.collapse_item(parent_item)
        await test_client.wait_for_refresh()
        assert not widget.is_item_expanded(parent_item)


async def test_tree_widget_item_removal() -> None:
    """Test TreeWidget item removal functionality."""
    widget = TreeWidget()
    item1 = TreeItem('Item 1')
    item2 = TreeItem('Item 2')
    item3 = TreeItem('Item 3')

    widget.add_top_level_item(item1)
    widget.add_top_level_item(item2)
    widget.add_top_level_item(item3)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial state
        assert widget.top_level_item_count() == 3

        # Test removing item
        widget.remove_item(item2)
        await test_client.wait_for_refresh()
        assert widget.top_level_item_count() == 2
        assert widget.top_level_item(0) == item1
        assert widget.top_level_item(1) == item3

        # Test taking item
        taken_item = widget.take_top_level_item(0)
        await test_client.wait_for_refresh()
        assert taken_item == item1
        assert widget.top_level_item_count() == 1
        assert widget.top_level_item(0) == item3


async def test_tree_widget_clear() -> None:
    """Test TreeWidget clear functionality."""
    widget = TreeWidget()
    item1 = TreeItem('Item 1')
    item2 = TreeItem('Item 2')

    widget.add_top_level_item(item1)
    widget.add_top_level_item(item2)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial state
        assert widget.top_level_item_count() == 2

        # Test clear
        widget.clear()
        await test_client.wait_for_refresh()
        assert widget.top_level_item_count() == 0


async def test_tree_item() -> None:
    """Test TreeItem basic functionality."""
    item = TreeItem('Test Item')

    # Test initial state
    assert item.text(0) == 'Test Item'
    assert item.child_count() == 0

    # Test setting text
    item.set_text(0, 'Updated Item')
    assert item.text(0) == 'Updated Item'

    # Test adding child
    child = TreeItem('Child Item')
    item.add_child(child)
    assert item.child_count() == 1
    assert item.child(0) == child

    # Test removing child
    item.remove_child(child)
    assert item.child_count() == 0


async def test_tree_item_hierarchy() -> None:
    """Test TreeItem hierarchy management."""
    root = TreeItem('Root')
    level1 = TreeItem('Level 1')
    level2 = TreeItem('Level 2')
    level3 = TreeItem('Level 3')

    # Build hierarchy
    root.add_child(level1)
    level1.add_child(level2)
    level2.add_child(level3)

    # Test hierarchy
    assert root.child_count() == 1
    assert root.child(0) == level1
    assert level1.child_count() == 1
    assert level1.child(0) == level2
    assert level2.child_count() == 1
    assert level2.child(0) == level3
    assert level3.child_count() == 0

    # Test parent relationships
    assert level1.parent() == root
    assert level2.parent() == level1
    assert level3.parent() == level2
    assert root.parent() is None


async def test_tree_item_expansion() -> None:
    """Test TreeItem expansion state."""
    item = TreeItem('Expandable Item')
    child = TreeItem('Child Item')
    item.add_child(child)

    # Test initial collapsed state
    assert not item.is_expanded()

    # Test expanding
    item.set_expanded(True)
    assert item.is_expanded()

    # Test collapsing
    item.set_expanded(False)
    assert not item.is_expanded()


async def test_tree_item_selection() -> None:
    """Test TreeItem selection state."""
    item = TreeItem('Selectable Item')

    # Test initial unselected state
    assert not item.is_selected()

    # Test selecting
    item.set_selected(True)
    assert item.is_selected()

    # Test deselecting
    item.set_selected(False)
    assert not item.is_selected()


async def test_tree_widget_client_interaction() -> None:
    """Test TreeWidget client interaction with timeout protection."""
    widget = TreeWidget()
    item1 = TreeItem('Item 1')
    item2 = TreeItem('Item 2')

    widget.add_top_level_item(item1)
    widget.add_top_level_item(item2)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial state
        assert widget.top_level_item_count() == 2

        # Test widget property changes
        widget.set_current_item(item1)
        await test_client.wait_for_refresh()
        assert widget.current_item() == item1

        # Verify client state reflects widget changes
        client_items = await test_client.execute_js('Array.from(document.querySelectorAll(".rio-tree-item")).length')
        assert client_items >= 2  # At least 2 items should be visible
