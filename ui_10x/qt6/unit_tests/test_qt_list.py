"""Qt6 counterpart of rio/widgets/unit_tests/test_list.py."""

import ui_10x.qt6.platform_implementation as ux
from ui_10x.qt6.testlib import qt_helpers as h


def _list(*items: str) -> tuple[ux.ListWidget, list]:
    clicked = []
    widget  = ux.ListWidget()
    widget.add_items(list(items))
    widget.clicked_connect(clicked.append)
    return h.show(widget), clicked


def _selected(widget: ux.ListWidget) -> list[str]:
    return [item.text() for item in widget.selected_items()]


def test_list_comprehensive() -> None:
    widget, clicked = _list('Item 1', 'Item 2', 'Item 3')
    assert widget.count() == 3

    h.click_item(widget, widget.item(0))
    assert [item.text() for item in clicked] == ['Item 1']
    assert _selected(widget) == ['Item 1']

    h.click_item(widget, widget.item(2))
    assert clicked[-1].text() == 'Item 3'
    assert _selected(widget) == ['Item 3']

    h.click_item(widget, widget.item(2))  #-- unlike in Rio, clicking the selected item keeps it selected
    assert len(clicked) == 3
    assert _selected(widget) == ['Item 3']

    widget.clear()
    assert widget.count() == 0
    assert _selected(widget) == []

    widget.add_item('New Item')
    assert widget.count() == 1
    h.click_item(widget, widget.item(0))
    assert clicked[-1].text() == 'New Item'


def test_list_item_management() -> None:
    widget, _ = _list('A', 'B', 'C')

    removed = widget.take_item(1)
    assert removed.text() == 'B'
    assert widget.count() == 2
    assert widget.item(1).text() == 'C'
    assert widget.item(1).row() == 1

    widget.add_item('Inserted')
    assert widget.count() == 3
    assert [item.text() for item in widget.find_items('Inserted', ux.MatchExactly)] == ['Inserted']


def test_list_disabled_interaction() -> None:
    widget, clicked = _list('Item 1', 'Item 2', 'Item 3')
    h.click_item(widget, widget.item(0))
    assert len(clicked) == 1
    assert _selected(widget) == ['Item 1']

    widget.set_enabled(False)
    h.click_item(widget, widget.item(1))
    assert len(clicked) == 1
    assert _selected(widget) == ['Item 1']

    widget.set_enabled(True)
    h.click_item(widget, widget.item(1))
    assert clicked[-1].text() == 'Item 2'
    assert _selected(widget) == ['Item 2']
