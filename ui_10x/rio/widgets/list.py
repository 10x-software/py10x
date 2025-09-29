from __future__ import annotations

from functools import partial

from core_10x.named_constant import Enum

import rio
import ui_10x.platform_interface as i
from ui_10x.rio.component_builder import Widget


class FindFlags(Enum):
    MATCH_EXACTLY = ()


class ListItem(Widget, i.ListItem):
    __slots__ = ('_list_widget',)
    s_component_class = rio.SimpleListItem
    args = dict(key=lambda kwargs: kwargs['text'])

    def _make_kwargs(self, **kwargs):
        kwargs = super()._make_kwargs(**kwargs)
        del kwargs['align_y']
        return kwargs

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._list_widget = None

    def row(self):
        if self._list_widget:
            return self._list_widget.row(self)

    def set_selected(self, selected: bool):
        return self._list_widget.set_selected(self, selected)


class ListWidget(Widget, i.ListWidget):
    __slots__ = ('_on_press',)
    s_component_class = rio.ListView
    s_default_kwargs = dict(selection_mode='single')
    s_unwrap_single_child = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self['grow_y'] = True

    def add_items(self, items: list[i.ListItem | str]):
        for item in items:
            self.add_item(item)

    def clicked_connect(self, bound_method):
        self._on_press = self.callback(bound_method)

    def _handle_on_press(self, item):
        if self._on_press:
            self._on_press(item)

    def add_item(self, item: ListItem | str):
        item = ListItem(text=item) if isinstance(item, str) else item
        item['on_press'] = partial(self._handle_on_press, item)
        item._list_widget = self
        self._kwargs[self.s_children_attr].append(item)
        self.force_update()

    def clear(self):
        self._kwargs['children'] = []
        self._kwargs['selected_items'] = []
        self.force_update()

    def find_items(self, text, flags):
        assert flags == FindFlags.MATCH_EXACTLY, 'only MatchExactly supported'
        return [item for item in self._kwargs[self.s_children_attr] if text == item['text']]

    def row(self, item: ListItem) -> int:
        return self._kwargs[self.s_children_attr].index(item)

    def take_item(self, row: int):
        try:
            return self._kwargs[self.s_children_attr].pop(row)
        finally:
            self.force_update()

    def set_selected(self, item: ListItem, selected: bool):
        # TODO: this is called from on-click handler for list item, which is
        # inefficient and duplicates rio built-in functionality
        selected_items = self.setdefault('selected_items', [])
        key = item['key']
        old_selected = key in selected_items
        print(selected_items, selected, old_selected, key)

        if not old_selected and selected:
            if self['selection_mode'] == 'single':
                selected_items = []
            selected_items.append(key)

        if old_selected and not selected:
            selected_items.remove(key)
        print(selected_items)
        self['selected_items'] = selected_items
