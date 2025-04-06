import rio
from typing import Optional, List, Set, Tuple


class TreeItem:
    __slots__ = ('_children', 'text', 'expanded', 'tooltip')

    def __init__(self, parent_node: Optional['TreeItem'] = None):
        if parent_node is not None:
            parent_node['children'].append(self)
        self._children = []
        self.text = {}
        self.expanded = False
        self.tooltip = {}

    def child_count(self):
        return len(self._children)

    def set_expanded(self, expanded: bool):
        self.expanded = expanded

    def set_text(self, col: int, text: str):
        self.text[col] = text

    def set_tool_tip(self, col: int, tooltip: str):
        self.tooltip[col] = tooltip

    def __getitem__(self, item: str):
        return getattr(self,f'_{item}')

class TreeWidget(rio.Component):
    # Properties from the builder
    column_count: int = 0
    header_labels: List[str] = []
    top_level_items: List[TreeItem] = []
    item_expanded_handler: callable = None
    item_clicked_handler: callable = None
    item_pressed_handler: callable = None
    item_changed_handler: callable = None

    # State properties defined at class level for Rio to manage
    expanded_items: Set[TreeItem] = set()
    editing_item: Optional[TreeItem] = None
    editing_column: Optional[int] = None
    persistent_editors: Set[Tuple[TreeItem, int]] = set()

    def build(self):
        """Render the tree widget."""
        # Header
        header = rio.Row(
            *[rio.Text(label, style="heading3") for label in self.header_labels],
            spacing=1,
        )

        # Tree nodes
        tree_nodes = [self.build_node(item) for item in self.top_level_items]

        return rio.ScrollContainer(
            content=rio.Column(
                header,
                *tree_nodes,
                spacing=1,
                align_x=0,
            ),
            grow_x=True,
            grow_y=True,
        )

    def build_node(self, item: TreeItem, depth: int = 0):
        """Build a single node and its children."""
        is_expanded = item in self.expanded_items
        has_children = bool(item._children)

        # Toggle button for expansion
        toggle_button = (
            rio.Button(
                icon="material/expand_more" if is_expanded else "material/chevron_right",
                on_press=lambda: self.toggle_expanded(item),
                # min_width=1.5,
                # min_height=1.5,
                # grow_x=False,
                # grow_y=False
                align_x=0,
                align_y=0,
            )
            if has_children
            else rio.Spacer(min_width=1.5,grow_x=False)
        )

        # Columns
        columns = []
        for col in range(self.column_count):
            value = item.text.get(col, '')
            tooltip = item.tooltip.get(col, '')
            is_editing = (
                (item, col) in self.persistent_editors or
                (self.editing_item == item and self.editing_column == col)
            )
            #value = f'{value}({col},{is_editing},{is_expanded},{item.child_count()})'
            if is_editing:
                def on_change(new_value: str, col=col):
                    item.set_text(col, new_value)
                    if self.item_changed_handler:
                        self.item_changed_handler(item, col)
                    self.stop_editing()
                columns.append(
                    rio.TextInput(
                        text=value,
                        on_change=on_change,
                        on_blur=self.stop_editing,
                        min_width=10,
                    )
                )
            else:
                def on_press(col=col):
                    if self.item_pressed_handler:
                        self.item_pressed_handler(item, col)
                def on_double_click(col=col):
                    self.start_editing(item, col)
                columns.append(
                    rio.PointerEventListener(
                        on_press=on_press,
                        #on_double_press=self.on_double_click,
                        content=rio.Tooltip(
                            tip=tooltip,
                            anchor=rio.Text(value)
                        )
                    )
                )

        # Node layout
        node_layout = rio.Row(
            rio.Spacer(min_width=depth * 2,grow_x=False),  # Indentation
            toggle_button,
            *columns,
            spacing=1,
        )

        # Include children if expanded
        if is_expanded and has_children:
            child_nodes = [self.build_node(child, depth + 1) for child in item._children]
            return rio.Column(node_layout, *child_nodes, spacing=0.5)
        return node_layout

    def toggle_expanded(self, item: TreeItem):
        """Toggle the expansion state of an item."""
        if item in self.expanded_items:
            self.expanded_items.remove(item)
        else:
            self.expanded_items.add(item)
            if self.item_expanded_handler:
                self.item_expanded_handler(item)
        self.expanded_items = self.expanded_items
        item.set_expanded(item in self.expanded_items)

    def start_editing(self, item: TreeItem, col: int):
        """Start editing an item in a specific column."""
        self.editing_item = item
        self.editing_column = col

    def stop_editing(self):
        """Stop editing the current item."""
        self.editing_item = None
        self.editing_column = None

    def open_persistent_editor(self, item: TreeItem, col: int):
        """Open a persistent editor for an item and column."""
        self.persistent_editors.add((item, col))

