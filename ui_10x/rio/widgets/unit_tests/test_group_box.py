import asyncio

import rio.testing.browser_client
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import CheckBox, GroupBox, Label, PushButton


async def test_group_box() -> None:
    """Test basic GroupBox widget functionality."""
    widget = GroupBox(title='Test Group')

    async with rio.testing.DummyClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial state
        assert widget['title'] == 'Test Group'

        # Test title change
        widget.set_title('Updated Group')
        await test_client.wait_for_refresh()
        assert widget['title'] == 'Updated Group'


async def test_group_box_with_children() -> None:
    """Test GroupBox widget with child widgets."""
    label = Label('Label inside group')
    checkbox = CheckBox('Checkbox inside group')
    button = PushButton('Button inside group')

    widget = GroupBox(None, 'Group with children', label, checkbox, button)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test title
        assert widget['title'] == 'Group with children'

        # Test children
        children = widget.get_children()
        assert len(children) == 3
        assert label in children
        assert checkbox in children
        assert button in children
        assert 4 == await test_client.execute_js('document.querySelectorAll(".rio-column .rio-text").length')
        assert 1 == await test_client.execute_js('document.querySelectorAll(".rio-button").length')


async def test_group_box_add_remove_children() -> None:
    """Test GroupBox widget adding and removing children."""
    widget = GroupBox(title='Dynamic Group')
    label = Label('Dynamic Label')
    button = PushButton('Dynamic Button')

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial empty state
        assert len(widget.get_children()) == 0
        assert 1 == await test_client.execute_js('document.querySelectorAll(".rio-column .rio-text").length')
        assert 0 == await test_client.execute_js('document.querySelectorAll(".rio-button").length')

        # Test adding children
        widget.add_children(label)
        await test_client.wait_for_refresh()
        assert len(widget.get_children()) == 1
        assert label in widget.get_children()
        assert 2 == await test_client.execute_js('document.querySelectorAll(".rio-column .rio-text").length')
        assert 0 == await test_client.execute_js('document.querySelectorAll(".rio-button").length')

        widget.add_children(button)
        await test_client.wait_for_refresh()
        assert len(widget.get_children()) == 2
        assert button in widget.get_children()
        assert 3 == await test_client.execute_js('document.querySelectorAll(".rio-column .rio-text").length')
        assert 1 == await test_client.execute_js('document.querySelectorAll(".rio-button").length')

        # Test removing children
        widget._kwargs['children'] = [child for child in widget._kwargs['children'] if child is not label]
        widget.force_update()
        await test_client.wait_for_refresh()
        assert len(widget.get_children()) == 1
        assert label not in widget.get_children()
        assert button in widget.get_children()
        assert 2 == await test_client.execute_js('document.querySelectorAll(".rio-column .rio-text").length')
        assert 1 == await test_client.execute_js('document.querySelectorAll(".rio-button").length')

        widget._kwargs['children'] = [child for child in widget._kwargs['children'] if child is not button]
        widget.force_update()
        await test_client.wait_for_refresh()
        assert len(widget.get_children()) == 0
        assert 1 == await test_client.execute_js('document.querySelectorAll(".rio-column .rio-text").length')
        assert 0 == await test_client.execute_js('document.querySelectorAll(".rio-button").length')


# async def test_group_box_enabled_disabled() -> None:
#     """Test GroupBox enabled/disabled state."""
#     widget = GroupBox(title = 'Enabled Group')
#     label = Label('Child Label')
#     widget.add_widget(label)
#
#     async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
#         await asyncio.sleep(0.5)
#
#         # Test initial enabled state
#         assert widget['is_sensitive']
#         assert label.is_enabled()
#
#         # Test disabling group (should disable children)
#         widget.set_enabled(False)
#         await test_client.wait_for_refresh()
#         assert not widget['is_sensitive']
#         assert not label.is_enabled()
#
#         # Test re-enabling
#         widget.set_enabled(True)
#         await test_client.wait_for_refresh()
#         assert widget['is_sensitive']
#         assert label.is_enabled()


async def test_group_box_client_interaction() -> None:
    """Test GroupBox widget client interaction with timeout protection."""
    widget = GroupBox(title='Client Test')
    label = Label('Content')
    widget.add_children(label)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial state
        assert widget['title'] == 'Client Test'
        assert len(widget.get_children()) == 1
        await check_title(widget, test_client)
        await check_label(label, test_client)

        # Test widget property changes
        widget.set_title('Updated Title')
        await test_client.wait_for_refresh()
        assert widget['title'] == 'Updated Title'

        # Verify client state reflects widget changes
        await check_title(widget, test_client)
        await check_label(label, test_client)

        # Test empty title
        widget.set_title('')
        await test_client.wait_for_refresh()
        assert widget['title'] == ''
        await check_title(widget, test_client)


async def check_label(label, test_client):
    assert 2 == await test_client.execute_js('document.querySelectorAll(".rio-column .rio-text").length')
    assert label['text'] == await test_client.execute_js('document.querySelectorAll(".rio-column .rio-text")[1].innerText')


async def check_title(widget, test_client):
    assert widget['title'] == await test_client.execute_js('document.querySelectorAll(".rio-column .rio-text")[0].innerText')
