import asyncio

import rio.testing
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import CheckBox, FormLayout, HBoxLayout, Label, LineEdit, PushButton, VBoxLayout


async def test_hbox_layout() -> None:
    """Test HBoxLayout widget functionality."""
    layout = HBoxLayout()
    label1 = Label('Left')
    label2 = Label('Right')
    button = PushButton('Button')

    layout.add_widget(label1)
    layout.add_widget(label2)
    layout.add_widget(button)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(layout)) as test_client:
        await asyncio.sleep(0.5)

        # Test children
        children = layout.get_children()
        assert len(children) == 3
        assert label1 in children
        assert label2 in children
        assert button in children

        # Test removing widgets
        layout.remove_widget(label1)
        await test_client.wait_for_refresh()
        assert len(layout.get_children()) == 2
        assert label1 not in layout.get_children()
        assert label2 in layout.get_children()
        assert button in layout.get_children()


async def test_vbox_layout() -> None:
    """Test VBoxLayout widget functionality."""
    layout = VBoxLayout()
    label1 = Label('Top')
    label2 = Label('Bottom')
    checkbox = CheckBox('Checkbox')

    layout.add_widget(label1)
    layout.add_widget(label2)
    layout.add_widget(checkbox)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(layout)) as test_client:
        await asyncio.sleep(0.5)

        # Test children
        children = layout.get_children()
        assert len(children) == 3
        assert label1 in children
        assert label2 in children
        assert checkbox in children

        # Test removing widgets
        layout.remove_widget(checkbox)
        await test_client.wait_for_refresh()
        assert len(layout.get_children()) == 2
        assert checkbox not in layout.get_children()
        assert label1 in layout.get_children()
        assert label2 in layout.get_children()


async def test_form_layout() -> None:
    """Test FormLayout widget functionality."""
    layout = FormLayout()
    label1 = Label('Name:')
    line_edit1 = LineEdit('John Doe')
    label2 = Label('Email:')
    line_edit2 = LineEdit('john@example.com')
    checkbox = CheckBox('Subscribe to newsletter')

    layout.add_widget(label1, line_edit1)
    layout.add_widget(label2, line_edit2)
    layout.add_widget(checkbox)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(layout)) as test_client:
        await asyncio.sleep(0.5)

        # Test children
        children = layout.get_children()
        assert len(children) == 5  # 2 labels + 2 line edits + 1 checkbox
        assert label1 in children
        assert line_edit1 in children
        assert label2 in children
        assert line_edit2 in children
        assert checkbox in children


async def test_layout_enabled_disabled() -> None:
    """Test layout enabled/disabled state."""
    layout = VBoxLayout()
    label = Label('Test Label')
    button = PushButton('Test Button')
    layout.add_widget(label)
    layout.add_widget(button)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(layout)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial enabled state
        assert layout.is_enabled()
        assert label.is_enabled()
        assert button.is_enabled()

        # Test disabling layout (should disable children)
        layout.set_enabled(False)
        await test_client.wait_for_refresh()
        assert not layout.is_enabled()
        assert not label.is_enabled()
        assert not button.is_enabled()

        # Test re-enabling
        layout.set_enabled(True)
        await test_client.wait_for_refresh()
        assert layout.is_enabled()
        assert label.is_enabled()
        assert button.is_enabled()


async def test_layout_clear() -> None:
    """Test clearing all widgets from layout."""
    layout = HBoxLayout()
    label1 = Label('Label 1')
    label2 = Label('Label 2')
    button = PushButton('Button')

    layout.add_widget(label1)
    layout.add_widget(label2)
    layout.add_widget(button)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(layout)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial state
        assert len(layout.get_children()) == 3

        # Test clearing layout
        layout.clear()
        await test_client.wait_for_refresh()
        assert len(layout.get_children()) == 0


async def test_nested_layouts() -> None:
    """Test nested layouts."""
    outer_layout = VBoxLayout()
    inner_layout = HBoxLayout()

    label1 = Label('Top')
    label2 = Label('Left')
    label3 = Label('Right')
    label4 = Label('Bottom')

    inner_layout.add_widget(label2)
    inner_layout.add_widget(label3)

    outer_layout.add_widget(label1)
    outer_layout.add_widget(inner_layout)
    outer_layout.add_widget(label4)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(outer_layout)) as test_client:
        await asyncio.sleep(0.5)

        # Test outer layout children
        outer_children = outer_layout.get_children()
        assert len(outer_children) == 3
        assert label1 in outer_children
        assert inner_layout in outer_children
        assert label4 in outer_children

        # Test inner layout children
        inner_children = inner_layout.get_children()
        assert len(inner_children) == 2
        assert label2 in inner_children
        assert label3 in inner_children
