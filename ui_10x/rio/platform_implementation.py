from functools import partial
from typing import Self

import webview
import ui_10x.platform_interface as i
import rio
import ui_10x.rio.components as rio_components
from core_10x.directory import Directory
from core_10x.named_constant import Enum


def init() -> rio.App:
    ...

class Object:
    ...

def signal_decl():
    ...

class TEXT_ALIGN(Enum):
    TOP = ()
    V_CENTER = ()
    BOTTOM = ()
    LEFT = ()
    CENTER = ()
    RIGHT = ()

class SCROLL(Enum):
    AS_NEEDED = ()

class SizePolicy(Enum):
    MINIMUM_EXPANDING = ()

    MinimumExpanding = MINIMUM_EXPANDING #TODO...

class _WidgetMixin:
    __slots__ = ()
    def set_style_sheet(self, sh: str):
        ...  # TODO

    def set_minimum_height(self, height: int):
        self._kwargs['min_height'] = height

    def set_minimum_width(self, width: int):
        self._kwargs['min_width'] = width

    def set_size_policy(self, x_policy, y_policy):
        assert y_policy == x_policy == SizePolicy.MinimumExpanding, 'only expanding size policy supported'
        self._kwargs['grow_x'] = True
        self._kwargs['grow_y'] = True

    def set_layout(self, layout: i.Layout):
        raise NotImplementedError

class ComponentBuilder:
    __slots__ = ('_children','_kwargs')

    s_component_class : type[rio.Component] = None
    s_forced_kwargs = {}
    def __init__(self, *children, **kwargs):
        self._children = list(children)
        self._kwargs = kwargs | self.s_forced_kwargs

    def add_children(self, *children):
        existing_children = set(self._children)
        self._children.extend(child for child in children if child not in existing_children)
        
    def with_children(self, *args):
        if not args:
            return self
        builder = self.__class__(*self._children, **self._kwargs)
        builder.add_children(*args)
        return builder

    def _build_children(self):
        return [ child() if isinstance(child,ComponentBuilder) else child for child in self._children ]

    def __call__(self):
        return self.s_component_class(*self._build_children(), **self._kwargs)

class Widget(ComponentBuilder, _WidgetMixin, i.Widget):
    __slots__ = ('_layout',)
    
    def __init__(self, *children, **kwargs):
        super().__init__(*children, **kwargs)
        self._layout = None
        
    def set_layout(self, layout: i.Layout):
        self._layout = layout
        
    def _build_children(self):
        return self._layout.with_children(*self._children)._build_children() if self._layout else super()._build_children()

class Label(Widget, i.Label):
    s_component_class = rio.Text
    s_forced_kwargs = {'selectable': False, 'align_x': 0}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self._children:
            self._children = [self._kwargs.pop('text','')]

    def set_text(self, text: str):
        self._children = [text]

class PushButton(Label,i.PushButton):
    s_component_class = rio.Button
    s_forced_kwargs = {}
    def clicked_connect(self, bound_method):
        self._kwargs['on_press'] = bound_method
    def set_flat(self, flat: bool):
        ... #TODO

class VBoxLayout(Widget, i.VBoxLayout):
    s_component_class = rio.Column

    def add_widget(self, widget, stretch=0, **kwargs):
        assert not kwargs, f'kwargs not supported: {kwargs}'
        if stretch:
            #widget._kwargs['grow_y'] = True
            ... #TODO
        self._children.append(widget)

    def add_layout(self, layout, **kwargs):
        assert not kwargs, f'kwargs not supported: {kwargs}'
        self._layout = layout

    def set_spacing(self, spacing: int):
        raise NotImplementedError

    def set_contents_margins(self, *args):
        raise NotImplementedError

class HBoxLayout(VBoxLayout,i.HBoxLayout):
    s_component_class = rio.Row

class Dialog(Widget,i.Dialog):
    s_component_class = rio.Column
    s_forced_kwargs = {'grow_x': True, 'grow_y': True}
    def __init__(self, parent=None, children=(), title=None, on_accept=None, on_reject=None, **kwargs):
        assert parent is None, 'parent not supported'
        super().__init__(*children, **kwargs)
        self.on_accept = self._wrapper(on_accept, accept=True)
        self.on_reject = self._wrapper(on_reject)
        self.window = None
        self.accepted = True
        self.title = title
        self._layout = VBoxLayout()

    def set_window_title(self, title: str):
        self.title = title

    def _wrapper(self, func, accept = False):
        def wrapper(*args):
            if func:
                func(*args)
            if self.window is not None:
                webview.windows[self.window].destroy()
                self.window = None
            self.accepted = accept
        return wrapper

    def reject(self):
        pass

    def done(self, result: int):
        self.accepted = bool(result)

    def _build_children(self):
        return self._layout.with_children( *self._children,
            HBoxLayout(
                PushButton('Accept', on_press=self.on_accept),
                PushButton('Reject', on_press=self.on_reject),
            )
        )._build_children()

    def exec(self):
        title = self.title or 'Dialog'
        app = rio.App(name=title, pages=[rio.ComponentPage(name=title, url_segment='', build=self)])
        self.window = len(webview.windows)
        app.run_in_window()
        return self.accepted

    def show(self):
        self.exec() #TODO...

    def set_window_flags(self, flags):
        raise NotImplementedError

    def set_modal(self, modal: bool):
        raise NotImplementedError



class RadioButton(Widget, i.RadioButton):
    __slots__ = ('_button_group')
    s_component_class = rio_components.RadioButton

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'label' not in self._kwargs:
            self._kwargs['label'] = self._children.pop(0)
        if 'selected_value' not in self._kwargs:
            self._kwargs['selected_value'] = None
        if 'value' not in self._kwargs:
            self._kwargs['value'] = self._kwargs['label']
        self._button_group = None

    def set_checked(self, checked: bool):
        self._kwargs['selected_value'] = self._kwargs['value'] if checked else None

    def on_select(self, value):
        if self._button_group:
            self._button_group.on_change(value)

    def __call__(self):
        button = self.s_component_class(
            **self._kwargs,
            on_select=self.on_select
        )
        if self._button_group:
            self._button_group._buttons.append(button)
        return button

class ButtonGroup(Widget, i.ButtonGroup):
    __slots__ = ('_buttons',)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._buttons = []

    def on_change(self, value):
        self._kwargs['selected_value'] = value
        for button in self._buttons:
            button.selected_value = value

    def add_button(self, button, id):
        if id < len(self._children):
            self._children[id] = button
        else:
            assert len(self._children) == id
            self._children.append(button)
        if button._kwargs['selected_value'] == button._kwargs['value']:
            self._kwargs['selected_value'] = button._kwargs['value']
        button._button_group = self

    def button(self, id: int) -> RadioButton:
        return self._children[id]

    def checked_id(self):
        #TODO: optimize
        selected = self._kwargs['selected_value']
        for i, button in enumerate(self._children):
            if button._kwargs['value'] == selected:
                return i
        return -1


class GroupBox(Widget, i.GroupBox):
    s_component_class = rio_components.GroupBox
    def __init__(self, *args, **kwargs):
        parent = None
        title = kwargs.pop('title', '')
        children = ()
        if len(args) >= 1:
            parent = args[0]
        if len(args) >= 2:
            assert not title, 'title specified twice'
            parent, title = args
            children = args[2:]
        super().__init__(*children, **kwargs)
        self._kwargs['title'] = title

    def set_title(self, title: str):
        self._kwargs['title'] = title

class LineEdit(Widget, i.LineEdit):
    s_component_class = rio.TextInput
    def set_text(self, text: str):
        self._kwargs['text'] = text

    def text(self):
        return self._kwargs['text']

    def text_edited_connect(self, bound_method):
        self._kwargs['on_change'] = bound_method

    def set_read_only(self, read_only: bool):
        self._kwargs['is_read_only'] = read_only

    def set_password_mode(self):
        self._kwargs['is_password'] = True

    def editing_finished_connect(self, bound_method):
        self._kwargs['on_confirm'] = bound_method

class Separator(Widget, i.Separator):
    s_component_class = rio_components.Separator
    s_forced_kwargs = {}

def separator(horizontal = True) -> Separator:
    return Separator() if horizontal else Separator(orientation='vertical')

class ListItem(Widget, i.ListItem):
    __slots__ = ('_list_widget',)
    s_component_class = rio.SimpleListItem

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._list_widget = None

    def row(self):
        if self._list_widget:
            return self._list_widget.row(self)

    def set_selected(self, selected: bool):
        return self._list_widget.set_selected(self, selected)

    #TODO: make selection visible

class FindFlags(Enum):
    MATCH_EXACTLY = ()

MatchExactly = FindFlags.MATCH_EXACTLY

class ListWidget(Widget, i.ListWidget):
    __slots__ = ('_on_press','_selected_item')
    s_component_class = rio.ListView

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_press = None
        self._selected_item = None

    def add_items(self, items):
        for item in items:
            self.add_item(item)

    def clicked_connect(self, bound_method):
        self._on_press = bound_method

    def _handle_on_press(self, item):
        if self._on_press:
            self._on_press(item)
        self.set_selected(item, True) #TODO: multi-select?

    def add_item(self, item):
        item = ListItem(text=item) if isinstance(item,str) else item
        item._kwargs['on_press'] = partial(self._handle_on_press, item)
        item._list_widget = self
        self._children.append(item)

    def clear(self):
        self._children.clear()

    def find_items(self, text, flags):
        assert flags == MatchExactly, 'only MatchExactly supported'
        return [item for item in self._children if text == item._kwargs['text']]

    def row(self, item: ListItem) -> int:
        return self._children.index(item)

    def take_item(self, row: int):
        return self._children.pop(row)

    def set_selected(self, item: ListItem, selected: bool):
        if selected:
            self._selected_item = item
        elif self._selected_item == item:
            self._selected_item = None

class TreeItem(rio_components.TreeItem, _WidgetMixin, i.TreeItem):
    __slots__ = ()

class TreeWidget(Widget, i.TreeWidget):
    __slots__ = ('col_count', 'header_labels', 'item_expanded_handler', 'item_clicked_handler', 'item_pressed_handler', 'item_changed_handler', 'component')
    s_component_class = rio_components.TreeWidget

    def __init__(self,*args, **kwargs):
        assert not args, f'args not supported: {args}'
        self.col_count = kwargs.pop('col_count', 0)
        self.header_labels = kwargs.pop('header_labels', [])
        self.item_expanded_handler = kwargs.pop('item_expanded_handler', None)
        self.item_clicked_handler = kwargs.pop('item_clicked_handler', None)
        self.item_pressed_handler = kwargs.pop('item_pressed_handler', None)
        self.item_changed_handler = kwargs.pop('item_changed_handler', None)
        self.component = None
        super().__init__(*args, **kwargs)

    def set_column_count(self, col_count: int):
        """Set the number of columns in the tree widget."""
        self.col_count = col_count

    def set_header_labels(self, labels: list):
        """Set the header labels for each column."""
        self.header_labels = labels

    def top_level_item_count(self) -> int:
        """Return the number of top-level items."""
        return len(self.top_level_items)

    def top_level_item(self, i: int) -> TreeItem:
        """Return the top-level item at index i."""
        return self.top_level_items[i]

    def resize_column_to_contents(self, col: int):
        """Adjust the width of the specified column (placeholder)."""
        # Rio handles layout automatically; this is a no-op unless custom widths are needed
        pass

    def item_expanded_connect(self, bound_method):
        """Connect a callback for when an item is expanded. Takes the item as an argument."""
        self.item_expanded_handler = bound_method

    def item_clicked_connect(self, bound_method):
        """Connect a callback for when an item is clicked. Takes item and column as arguments."""
        self.item_clicked_handler = bound_method

    def item_pressed_connect(self, bound_method):
        """Connect a callback for when an item is pressed. Takes item and column as arguments."""
        self.item_pressed_handler = bound_method

    def item_changed_connect(self, bound_method):
        """Connect a callback for when an item's data changes. Takes item and column as arguments."""
        self.item_changed_handler = bound_method

    def edit_item(self, item: TreeItem, col: int):
        """Start editing the specified item in the given column (placeholder)."""
        self.component.start_editing(item, col)

    def open_persistent_editor(self, item: TreeItem, col: int):
        """Open a persistent editor for the specified item and column (placeholder)."""
        self.component.open_persistent_editor(item, col)

    def add_top_level_item(self, item: TreeItem):
        """Add a top-level item to the tree (helper method)."""
        self._children.append(item)

    def __call__(self):
        """Build and return the TreeWidgetComponent."""
        assert not self.component, 'TreeWidget already built'
        self.component = self.s_component_class(
            column_count=self.col_count,
            header_labels=self.header_labels,
            top_level_items=self._children,
            item_expanded_handler=self.item_expanded_handler,
            item_clicked_handler=self.item_clicked_handler,
            item_pressed_handler=self.item_pressed_handler,
            item_changed_handler=self.item_changed_handler,
            **self._kwargs
        )
        return self.component
