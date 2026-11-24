"""Qt6 counterpart of rio/widgets/unit_tests/test_splitter.py.

A QSplitter starts with each pane's size hint times its stretch factor, when first laid out; a resize keeps the panes'
current proportions, whatever the factors. Panes with the same text have the same size hint in any font.
"""

import ui_10x.qt6.platform_implementation as ux
from ui_10x.qt6.testlib import qt_helpers as h


def _splitter(*stretch: int, labels = ('A', 'A'), width: int = 600) -> ux.Splitter:
    widget = ux.Splitter(ux.Horizontal)
    for text in labels:
        widget.add_widget(ux.Label(text))
    for i, factor in enumerate(stretch):
        widget.set_stretch_factor(i, factor)
    widget.resize(width, 100)
    return h.show(widget)


def test_equal_proportions_split_evenly() -> None:
    widget  = _splitter(1, 1)
    a, b    = widget.sizes()
    assert abs(a - b) <= 1
    assert a + b + widget.handle_width() == widget.width()


def test_proportions_are_honored() -> None:
    a, b = _splitter(3, 1).sizes()
    assert abs(a - 3 * b) <= 3, f'expected 3:1, got {a}:{b}'


def test_stretch_factors_multiply_the_size_hints() -> None:
    widget      = _splitter(1, 2, labels = ('A' * 12, 'A' * 4))
    weights     = [widget.widget(0).sizeHint().width(), 2 * widget.widget(1).sizeHint().width()]
    total       = sum(widget.sizes())
    expected    = [total * weight / sum(weights) for weight in weights]
    assert all(abs(size - want) <= 2 for size, want in zip(widget.sizes(), expected, strict = True)), (widget.sizes(), expected)


def _resize(widget: ux.Splitter, width: int) -> list[int]:
    widget.resize(width, 100)
    ux.Application.processEvents()
    return widget.sizes()


def test_resize_keeps_the_proportions() -> None:
    widget  = _splitter(3, 1)
    a, b    = _resize(widget, 1000)
    assert abs(a - 3 * b) <= 3, f'expected 3:1, got {a}:{b}'

    widget.setSizes([a // 2, a // 2])  #-- as if the handle were dragged
    a, b = widget.sizes()
    assert abs(a - b) <= 1

    a, b = _resize(widget, 1400)
    assert abs(a - b) <= 12, f'expected the dragged proportions, not 3:1, got {a}:{b}'


def test_stretch_factors_set_after_showing_change_nothing() -> None:
    widget = _splitter()
    before = widget.sizes()
    widget.set_stretch_factor(0, 3)
    widget.set_stretch_factor(1, 1)
    ux.Application.processEvents()
    assert widget.sizes() == before


def test_handle_is_fixed() -> None:
    widget = _splitter(3, 1)
    widget.set_handle_width(9)
    _resize(widget, 1000)
    assert widget.handle_width() == 9
    assert sum(widget.sizes()) + 9 == widget.width()


def test_replace_widget() -> None:
    widget  = _splitter(1, 1)
    pane    = ux.Label('C')
    widget.replace_widget(1, pane)
    assert widget.count() == 2
    assert widget.widget(1) is pane


def test_single_child_has_no_handle() -> None:
    widget = _splitter(1, labels = ('only',))
    assert widget.count() == 1
    assert widget.sizes() == [widget.width()]  #-- handle(0) exists in Qt but is never shown or sized
