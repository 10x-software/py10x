"""Minimal Rio TableView: flat header + grid of styled cells (Phase 1).

Supports the guess_word surface: construct from entities, horizontalHeader stub,
and render_traitable. Does not import table_header_view / StandardItemModel.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

from core_10x.traitable import Traitable

import rio
from ui_10x.rio.component_builder import Widget
from ui_10x.rio.style_sheet import StyleSheet
from ui_10x.traitable_view import TraitableView

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

# One cell: (display_text, background_color, foreground_color)
_Cell = tuple[str, str, str]
_Row = tuple[_Cell, ...]


class _HorizontalHeader:
    """Qt-compatible stub; stretch/resize are no-ops until Phase 2."""

    def setStretchLastSection(self, _stretch: bool) -> None:  # noqa: N802 — Qt API
        pass

    def set_stretch_last_section(self, stretch: bool) -> None:
        self.setStretchLastSection(stretch)


def _flat_columns(header: dict) -> list[tuple[str, str]]:
    """Leaf columns only: (trait_name, label). Nested headers are Phase 2."""
    cols: list[tuple[str, str]] = []
    for name, label_or_subtree in header.items():
        if isinstance(label_or_subtree, str):
            cols.append((name, label_or_subtree))
    return cols


def _loads_sheet(sheet: str) -> dict[str, str]:
    """Local CSS parse — avoid importing ui_10x.utils (circular via platform)."""
    res: dict[str, str] = {}
    for pair in (sheet or '').split(';'):
        pair = pair.strip()
        if not pair:
            continue
        name_value = pair.split(':', 1)
        if len(name_value) == 2:
            res[name_value[0].strip()] = name_value[1].strip()
    return res


def _cell_component(text: str, bg: str, fg: str) -> rio.Component:
    # Non-breaking space so empty guess cells keep a visible box.
    display = text if (text and text.strip()) else '\u00a0'
    content = rio.Text(
        display,
        justify='center',
        selectable=False,
        font_weight='bold',
        fill=StyleSheet.parse_color(fg),
    )
    return rio.Rectangle(
        content=rio.Container(content, align_x=0.5, align_y=0.5),
        fill=StyleSheet.parse_color(bg),
        corner_radius=0.2,
        min_width=2.2,
        min_height=2.2,
        margin=0.1,
        grow_x=True,
    )


class TraitableTableGrid(rio.Component):
    """Rio state-driven grid. Assign ``rows`` / ``rev`` to refresh in-session."""

    rev: int = 0
    headers: tuple[str, ...] = ()
    rows: tuple[_Row, ...] = ()

    def build(self) -> rio.Component:
        header = [rio.Text(h, font_weight='bold', justify='center', selectable=False) for h in self.headers]
        body = [[_cell_component(t, bg, fg) for t, bg, fg in row] for row in self.rows]
        if not self.headers:
            return rio.Text('(no columns)', italic=True)
        return rio.Grid(
            header,
            *body,
            row_spacing=0.25,
            column_spacing=0.25,
            grow_x=True,
            key=f'grid_{self.rev}',
        )


class TableView(Widget):
    """Rio stand-in for Qt ``QTableView`` + Traitable Model (Phase 1)."""

    __slots__ = ('_hv', '_rev', 'entities', 'header_labels', 'trait_names', 'view')
    # Outer shell only; real UI is TraitableTableGrid (see build).
    s_component_class = rio.Column
    s_unwrap_single_child = True
    s_default_kwargs = {'grow_x': True, 'grow_y': True, 'align_y': 0}

    def __init__(self, entities_or_class, view: TraitableView | None = None):
        assert entities_or_class, 'first arg must not be empty'

        if inspect.isclass(entities_or_class):
            assert issubclass(entities_or_class, Traitable), 'first arg is a class, but not a subclass of Traitable'
            proto = entities_or_class
            entities: list = []
        else:
            entities = list(entities_or_class) if not isinstance(entities_or_class, list) else entities_or_class
            proto = entities[0].__class__

        if not view:
            view = TraitableView.default(proto)

        columns = _flat_columns(view.header)
        self.view = view
        self.entities = entities
        self.trait_names = [name for name, _ in columns]
        self.header_labels = [label for _, label in columns]
        self._hv = _HorizontalHeader()
        self._rev = 0
        super().__init__()

    def horizontalHeader(self) -> _HorizontalHeader:  # noqa: N802 — Qt API
        return self._hv

    def _cell_text_and_style(self, entity: Traitable, trait_name: str) -> tuple[str, str]:
        trait = entity.__class__.trait(trait_name)
        if not trait:
            return '', ''
        value = entity.get_trait_value(trait)
        text = trait.to_str(value) if value is not None else ''
        sh = entity.get_style_sheet(trait) or ''
        return text, sh

    def _snapshot_rows(self) -> tuple[_Row, ...]:
        rows: list[_Row] = []
        for entity in self.entities:
            cells: list[_Cell] = []
            for name in self.trait_names:
                text, sh = self._cell_text_and_style(entity, name)
                data = _loads_sheet(sh)
                cells.append(
                    (
                        text,
                        data.get('background-color') or 'lightgray',
                        data.get('color') or 'black',
                    )
                )
            rows.append(tuple(cells))
        return tuple(rows)

    def _ensure_grid(self) -> TraitableTableGrid:
        grid = self.subcomponent
        if not isinstance(grid, TraitableTableGrid):
            grid = TraitableTableGrid(
                rev=self._rev,
                headers=tuple(self.header_labels),
                rows=self._snapshot_rows(),
                key=f'table_grid_{id(self)}',
            )
            self.subcomponent = grid
        return grid

    def build(self) -> rio.Component:
        grid = self._ensure_grid()
        grid.headers = tuple(self.header_labels)
        grid.rows = self._snapshot_rows()
        return grid

    def render_traitable(self, row: int, entity: Traitable | None):
        """Refresh one row after an in-place update (guess_word passes entity=None)."""
        if entity is not None and 0 <= row < len(self.entities):
            self.entities[row] = entity
        self._rev += 1
        rows = self._snapshot_rows()
        grid = self.subcomponent
        if isinstance(grid, TraitableTableGrid):
            grid.headers = tuple(self.header_labels)
            grid.rows = rows
            grid.rev = self._rev
            return
        self.force_update()

    def extend_data(self, data: Iterable[Traitable] | Sequence[Traitable]):
        """Append rows and refresh. Phase 2 may add resize-to-contents parity."""
        if data:
            self.entities.extend(data)
            self.render_traitable(-1, None)
