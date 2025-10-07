from __future__ import annotations

from functools import partial

import ui_10x.platform_interface as i
import ui_10x.rio.components as rio_components
from ui_10x.rio.component_builder import Widget


class TreeItem(Widget, i.TreeItem):
    __slots__ = ('handlers',)
    s_component_class = rio_components.RioTreeItem
    s_pass_children_in_kwargs = True

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
        super().set_text(text)

    # noinspection PyMethodOverriding
    def set_tool_tip(self, col: int, text: str):
        super().set_tool_tip(text)


class TreeWidget(Widget, i.TreeWidget):
    __slots__ = ('handlers',)
    s_component_class = rio_components.RioTreeView
    s_default_kwargs = dict(selection_mode='single')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.handlers = {}

    def set_column_count(self, col_count: int):
        """Set the number of columns in the tree widget."""
        assert col_count in [1, 2], 'col_count must be 1 or 2'
        self['col_count'] = col_count

    def set_header_labels(self, labels: list):
        """Set the header labels for each column."""
        self['header_labels'] = labels

    def top_level_item_count(self) -> int:
        """Return the number of top-level items."""
        return len(self.get_children())

    def top_level_item(self, i: int) -> TreeItem:
        """Return the top-level item at index i."""
        return self.get_children()[i]

    def resize_column_to_contents(self, col: int):
        """Adjust the width of the specified column (placeholder)."""
        pass

    def item_expanded_connect(self, bound_method):
        self.handlers['on_item_expand'] = self.callback(bound_method)

    def item_clicked_connect(self, bound_method):
        # self.handlers['on_item_double_press'] = bound_method
        self.handlers['on_item_press'] = self.callback(bound_method)

    def item_pressed_connect(self, bound_method):
        self.handlers['on_item_press'] = bound_method

    def item_changed_connect(self, bound_method):
        raise NotImplementedError

    def edit_item(self, item: TreeItem, col: int):
        """Start editing the specified item in the given column (placeholder)."""
        # self.component.start_editing(item, col)
        raise NotImplementedError

    def open_persistent_editor(self, item: TreeItem, col: int):
        """Open a persistent editor for the specified item and column (placeholder)."""
        # self.component.open_persistent_editor(item, col)
        raise NotImplementedError

    def add_top_level_item(self, item: TreeItem):
        """Add a top-level item to the tree (helper method)."""
        self.get_children().append(item)
