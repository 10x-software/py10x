from __future__ import annotations

from typing import Literal

import rio


class RioTreeItem(rio.Component):
    """same as SimpleTreeItem, but includes tooltip and supports double-click"""

    text: str = ''
    on_double_press: rio.EventHandler[[]] = None
    on_press: rio.EventHandler[[]] = None
    on_change: rio.EventHandler[[]] = None
    tooltip: str | None = None
    editable: bool = False
    editing: bool = False
    children: list[RioTreeItem] = []
    is_expanded: bool = False

    def build_primary_text(self):
        if not self.editing:
            return rio.Text(self.text, justify='left', selectable=False)
        return rio.TextInput(
            self.text,
            align_x=0,  # justify left?
            on_confirm=self.handle_edit_confirm,
        )

    def build_content(self):
        content = self.build_primary_text()
        if self.tooltip:
            content = rio.Row(content, rio.Tooltip(anchor=content, tip=self.tooltip))
        if self.on_double_press:
            content = rio.PointerEventListener(content, on_double_press=self.handle_double_press)
        return content

    def handle_double_press(self, ev: rio.PointerEvent):
        if self.editable:
            self.editing = True
        if self.on_double_press:
            self.on_double_press()

    def handle_edit_confirm(self, text):
        assert self.editing
        self.text = text
        if self.on_change:
            self.on_change()

    def build(self):
        return rio.SimpleTreeItem(
            content=self.build_content(),
            children=[child.build() for child in self.children],
            is_expanded=self.is_expanded,
            on_press=self.on_press,
        )

class RioTreeView(rio.Component):
    """makes item-level callbacks available on the tree level"""

    children: list[rio.Component] = None
    selection_mode: Literal['none', 'single', 'multiple'] = ('none',)
    col_count: int = 1
    header_labels: list[str] | None = None

    def __post__init__(self):
        if self.header_labels is None:
            self.header_labels = ['header']

    def build(self):
        return rio.TreeView(
            *[item.build() for item in self.children],  # TODO: should not need to build each item
            selection_mode=self.selection_mode,
        )
