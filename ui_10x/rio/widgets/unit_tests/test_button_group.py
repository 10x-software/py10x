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
