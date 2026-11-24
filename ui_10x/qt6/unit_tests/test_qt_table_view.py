"""Qt6 counterpart of rio/unit_tests/test_table_view.py."""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

import ui_10x.platform_interface as i
import ui_10x.table_view
from core_10x.exec_control import CACHE_ONLY
from core_10x.traitable import RT, T, Traitable, Ui
from ui_10x.qt6.testlib import qt_helpers as h
from ui_10x.qt6.table_view import Model
from ui_10x.table_view import TableView


class StyledCell(Traitable):
    letter: str = T(Ui(label = 'L'))
    bg: str     = RT(T.HIDDEN, default = 'lightgray')
    fg: str     = RT(T.HIDDEN, default = 'black')

    def letter_style_sheet(self):
        return T.colors(self.bg, self.fg)


def _cell(table, row: int, role = Qt.ItemDataRole.DisplayRole):
    model = table.model()
    return model.data(model.index(row, 0), role)


def _painted(table, row: int, *colors: str) -> str:
    """Which of `colors` the cell's background is drawn nearest to: a style blends the role color a little."""
    rect    = table.visual_rect(table.model().index(row, 0))
    drawn   = table.viewport().grab().toImage().pixelColor(rect.left() + 2, rect.top() + 2).getRgb()[:3]
    return min(colors, key = lambda c: sum((a - b) ** 2 for a, b in zip(drawn, QColor(c).getRgb()[:3], strict = True)))


def test_table_view_construct_and_render() -> None:
    with CACHE_ONLY():
        rows    = [StyledCell(letter = 'A', bg = 'darkgreen', fg = 'white'), StyledCell(letter = 'B')]
        table   = TableView(rows)
        assert isinstance(table, i.TableView)
        model = table.model()
        assert list(model.col2name.values()) == ['letter']  #-- HIDDEN traits get no column
        assert model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) == 'L'
        table.horizontalHeader().setStretchLastSection(False)

        assert _cell(table, 0) == 'A'
        assert _cell(table, 0, Qt.ItemDataRole.BackgroundRole).name() == QColor('darkgreen').name()
        assert _cell(table, 0, Qt.ItemDataRole.ForegroundRole).name() == QColor('white').name()

        changed = []
        model.dataChanged.connect(lambda first, last: changed.append((first.row(), last.row())))
        rows[1].letter  = 'Z'
        rows[1].bg      = 'white'
        table.render_traitable(1, None)
        assert changed == [(1, 1)]
        assert _cell(table, 1) == 'Z'
        assert _cell(table, 1, Qt.ItemDataRole.BackgroundRole).name() == QColor('white').name()


def test_table_view_render_traitable_repaints() -> None:
    with CACHE_ONLY():
        row     = StyledCell(letter = 'X')
        table   = h.show(TableView([row]))
        assert _painted(table, 0, 'lightgray', 'darkgreen') == 'lightgray'

        row.letter  = 'Y'
        row.bg      = 'darkgreen'
        table.render_traitable(0, None)
        h.wait_until(lambda: _painted(table, 0, 'lightgray', 'darkgreen') == 'darkgreen', message = 'the repainted background')
        assert _cell(table, 0) == 'Y'


def test_table_view_extend_data() -> None:
    with CACHE_ONLY():
        table = TableView(StyledCell)
        assert table.model().rowCount() == 0
        assert table.model().columnCount() == 0  #-- no columns until there is data

        table.extend_data([StyledCell(letter = 'P'), StyledCell(letter = 'Q')])
        assert table.model().rowCount() == 2
        assert [_cell(table, r) for r in range(2)] == ['P', 'Q']


def test_table_view_dispatcher_qt() -> None:
    """``ui_10x.table_view`` follows the Qt impl, whose header is ``ui_10x.table_header_view``."""
    assert TableView.__module__ == 'ui_10x.qt6.table_view'
    assert ui_10x.table_view.Model is Model
    assert 'ui_10x.table_header_view' in sys.modules
