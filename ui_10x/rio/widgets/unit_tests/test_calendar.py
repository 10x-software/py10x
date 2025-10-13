import asyncio
from datetime import date

import dateutil.parser
import rio.testing
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import CalendarWidget

find_selected_date = (
    'document.querySelector(".rio-calendar-selected-day").textContent + " " + document.querySelector(".rio-calendar-year-month-display").textContent'
)


async def verify_content(widget, test_client):
    selected_date = await test_client.execute_js(find_selected_date)

    assert dateutil.parser.parse(selected_date).date() == widget.selected_date()


async def test_calendar_comprehensive() -> None:
    """Test CalendarWidget with comprehensive client-widget interaction verification."""
    widget = CalendarWidget()
    test_date = date(2024, 6, 15)

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # 1) Verify client shows widget value (initial state)
        assert widget.selected_date() == date.today()

        # Verify client shows the expected date
        await verify_content(widget, test_client)

        # 2) Modify widget value and verify client reflects it
        widget.set_selected_date(test_date)
        await test_client.wait_for_refresh()
        assert widget.selected_date() == test_date

        # Verify client shows the expected date
        await verify_content(widget, test_client)

        # Test another date change
        new_date = date(2024, 8, 20)
        widget.set_selected_date(new_date)
        await test_client.wait_for_refresh()
        assert widget.selected_date() == new_date

        # Verify client shows the new expected date
        await verify_content(widget, test_client)


async def test_calendar_disabled_interaction() -> None:
    """Test CalendarWidget disabled state."""
    widget = CalendarWidget()

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial enabled state
        assert widget['is_sensitive']

        # Disable widget
        widget.set_enabled(False)
        await test_client.wait_for_refresh()
        assert not widget['is_sensitive']
        await verify_content(widget, test_client)

        # Test that date changes still work (programmatic changes are allowed)
        widget.set_selected_date(date(2024, 12, 25))
        await test_client.wait_for_refresh()
        assert widget.selected_date() == date(2024, 12, 25)

        # Verify client shows the expected date even when disabled
        await verify_content(widget, test_client)

        # Re-enable widget
        widget.set_enabled(True)
        await test_client.wait_for_refresh()
        assert widget['is_sensitive']

        # Test that date changes continue to work
        widget.set_selected_date(date(2024, 1, 1))
        await test_client.wait_for_refresh()
        assert widget.selected_date() == date(2024, 1, 1)

        # Verify client shows the final expected date
        await verify_content(widget, test_client)


async def test_calendar_basic_functionality() -> None:
    """Test CalendarWidget basic functionality."""
    widget = CalendarWidget()

    async with rio.testing.DummyClient(lambda: DynamicComponent(widget)) as test_client:
        await asyncio.sleep(0.5)

        # Test initial state
        assert widget is not None
        assert widget['is_sensitive']

        # Test date setting
        test_date = date(2024, 3, 10)
        widget.set_selected_date(test_date)
        await test_client.wait_for_refresh()
        assert widget.selected_date() == test_date

        # Test enabled/disabled state
        widget.set_enabled(False)
        await test_client.wait_for_refresh()
        assert not widget['is_sensitive']

        widget.set_enabled(True)
        await test_client.wait_for_refresh()
        assert widget['is_sensitive']
