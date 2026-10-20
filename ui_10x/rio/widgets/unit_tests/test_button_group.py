import asyncio

import rio.testing.browser_client
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets.button_group import ButtonGroup, RadioButton


async def test_button_group() -> None:
    group = ButtonGroup()
    btn1 = RadioButton(label='A', value='A')
    btn2 = RadioButton(label='B', value='B')
    group.add_button(btn1, 0)
    group.add_button(btn2, 1)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(group)) as test_client:
        await asyncio.sleep(0.5)
        # Initially, nothing selected
        assert group.checked_id() == -1

        # Select first button
        btn1.set_checked(True)
        await test_client.wait_for_refresh()
        assert group.checked_id() == 0

        # Select second button
        btn2.set_checked(True)
        await test_client.wait_for_refresh()
        assert group.checked_id() == 1

        # Deselect second button
        btn2.set_checked(False)
        await test_client.wait_for_refresh()
        assert group.checked_id() == -1


async def test_radio_button_label_click_selects() -> None:
    """Clicking the label (not only the icon) must select the radio."""
    group = ButtonGroup()
    btn1 = RadioButton(label='ANY', value='ANY')
    btn2 = RadioButton(label='LEAF', value='LEAF')
    group.add_button(btn1, 0)
    group.add_button(btn2, 1)
    btn1.set_checked(True)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(group)) as test_client:
        await asyncio.sleep(0.5)
        assert group.checked_id() == 0

        await test_client.playwright_page.get_by_text('LEAF', exact=True).click()
        await asyncio.sleep(0.5)
        assert group.checked_id() == 1
        assert btn2['checked'] is True
        assert btn1['checked'] is False

        # Re-clicking the selected radio must keep it selected (no toggle-off).
        await test_client.playwright_page.get_by_text('LEAF', exact=True).click()
        await asyncio.sleep(0.5)
        assert group.checked_id() == 1
