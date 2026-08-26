from __future__ import annotations

from functools import partial

import rio
import ui_10x.platform_interface as i
import ui_10x.rio.components as rio_components
from ui_10x.rio.component_builder import Widget


class TreeItem(Widget, i.TreeItem):
    __slots__ = ('handlers',)
    # RioTreeItem is kwargs allowlist only — see rio/components/tree_view.py.
    s_component_class = rio_components.RioTreeItem
    s_pass_children_in_kwargs = True
    s_unwrap_single_child = False

    def __init__(self, parent: TreeWidget | TreeItem, *args, **kwargs):
        super().__init__(*args, **kwargs)
        parent[self.s_children_attr] = parent[self.s_children_attr] + [self]
        self.handlers = parent.handlers
        for name, callback in self.handlers.items():
            self[name.replace('_item_', '_')] = partial(callback, self)

    def set_expanded(self, expanded: bool):
        self['is_expanded'] = expanded

    # noinspection PyMethodOverriding
    def set_text(self, col: int, text: str):
        # Single-column for now; col>0 (description) is ignored.
        if col == 0:
            self['text'] = text

    # noinspection PyMethodOverriding
    def set_tool_tip(self, col: int, text: str):
        self['tooltip'] = text


class TreeWidget(Widget, i.TreeWidget):
    __slots__ = ('col_count', 'handlers', 'header_labels')
    s_component_class = rio.TreeView
    s_pass_children_in_kwargs = False
    s_unwrap_single_child = False
    s_default_kwargs = {'selection_mode': 'none'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.handlers = {}
        self.col_count = 1
        self.header_labels: list[str] | None = None

    def _to_simple_tree_item(self, item: TreeItem) -> rio.SimpleTreeItem:
        """Emit a SimpleTreeItem in this build (do not reuse cross-build Components)."""
        text = item.get('text', '') or ''
        content: rio.Component = rio.Text(text, justify='left', selectable=False)
        if tooltip := item.get('tooltip'):
            content = rio.Tooltip(anchor=content, tip=tooltip)
        if on_double := item.get('on_double_press'):
            content = rio.PointerEventListener(content, on_double_press=on_double)

        kids = [self._to_simple_tree_item(child) for child in item._get_children() if isinstance(child, TreeItem)]

        def on_expansion_change(event) -> None:
            item['is_expanded'] = event.is_expanded

        press = item.get('on_press')
        live: dict = {'item': None}

        def on_press() -> None:
            # Non-leaf row click opens the node (chevron still toggles). Always run
            # select_hook so ANY/SUBDIR can select the directory.
            d = getattr(item, 'dir', None)
            if d is not None and not d.is_leaf() and not bool(item.get('is_expanded', False)):
                item['is_expanded'] = True
                if live['item'] is not None:
                    live['item'].is_expanded = True
            if press:
                press()

        built = rio.SimpleTreeItem(
            content=content,
            children=kids,
            is_expanded=bool(item.get('is_expanded', False)),
            on_press=on_press if press else None,
            on_expansion_change=on_expansion_change,
            key=id(item),
        )
        live['item'] = built
        return built

    def _build_children(self, session: rio.Session):
        # Same idea as Layout._build_children: materialize children for create_component.
        return [self._to_simple_tree_item(child) for child in self._get_children() if isinstance(child, TreeItem)]

    def build(self, session: rio.Session) -> rio.Component:
        tree = super().build(session)
        labels = self.header_labels
        if not labels:
            return tree
        # Match Qt QTreeWidget header (e.g. Directory.show_value() → "Animals").
        if len(labels) == 1:
            header: rio.Component = rio.Text(labels[0], font_weight='bold', justify='left')
        else:
            header = rio.Row(
                *(rio.Text(label, font_weight='bold', justify='left', grow_x=True) for label in labels),
                spacing=1,
            )
        return rio.Column(header, tree, spacing=0.3, grow_y=True)

    def set_column_count(self, col_count: int):
        """Store column count (rio.TreeView is single-column; multi-col is a no-op)."""
        assert col_count in [1, 2], 'col_count must be 1 or 2'
        self.col_count = col_count

    def set_header_labels(self, labels: list):
        """Store header labels (rio.TreeView has no header row yet)."""
        self.header_labels = labels

    def top_level_item_count(self) -> int:
        """Return the number of top-level items."""
        return len(self.get_children())

    def top_level_item(self, i: int) -> TreeItem:
        """Return the top-level item at index i."""
        return self.get_children()[i]

    def resize_column_to_contents(self, col: int):
        """Adjust the width of the specified column (placeholder)."""

    def item_expanded_connect(self, bound_method):
        self.handlers['on_item_expand'] = self.callback(bound_method)

    def item_clicked_connect(self, bound_method):
        self.handlers['on_item_press'] = self.callback(bound_method)

    def item_pressed_connect(self, bound_method):
        self.handlers['on_item_press'] = bound_method

    def item_changed_connect(self, bound_method):
        raise NotImplementedError

    def edit_item(self, item: TreeItem, col: int):
        """Qt-only: Rio TreeView / SimpleTreeItem have no inline edit API."""
        raise NotImplementedError

    def open_persistent_editor(self, item: TreeItem, col: int):
        """Qt-only: Rio TreeView / SimpleTreeItem have no inline edit API."""
        raise NotImplementedError

    def add_top_level_item(self, item: TreeItem):
        """Add a top-level item to the tree (helper method)."""
        self.get_children().append(item)
