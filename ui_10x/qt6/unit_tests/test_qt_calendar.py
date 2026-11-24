"""Qt6 counterpart of rio/widgets/unit_tests/test_calendar.py."""

from datetime import date

import ui_10x.qt6.platform_implementation as ux
from ui_10x.qt6.testlib import qt_helpers as h


def test_calendar_comprehensive() -> None:
    widget = h.show(ux.CalendarWidget())
    assert widget.selected_date() == date.today()

    widget.set_selected_date(date(2024, 6, 15))
    assert widget.selected_date() == date(2024, 6, 15)
    assert (widget.month_shown(), widget.year_shown()) == (6, 2024)

    widget.set_selected_date(date(2024, 8, 20))
    assert widget.selected_date() == date(2024, 8, 20)
    assert widget.month_shown() == 8


def test_calendar_disabled_interaction() -> None:
    widget = h.show(ux.CalendarWidget())
    assert widget.is_enabled()

    widget.set_enabled(False)
    assert not widget.is_enabled()
    widget.set_selected_date(date(2024, 12, 25))  #-- programmatic changes still apply
    assert widget.selected_date() == date(2024, 12, 25)

    widget.set_enabled(True)
    widget.set_selected_date(date(2024, 1, 1))
    assert widget.selected_date() == date(2024, 1, 1)


def test_calendar_basic_functionality() -> None:
    widget = ux.CalendarWidget()
    widget.set_grid_visible(True)
    assert widget.is_grid_visible()

    widget.set_selected_date(date(2024, 3, 10))
    assert widget.selected_date() == date(2024, 3, 10)
