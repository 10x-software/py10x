from __future__ import annotations

from dataclasses import KW_ONLY
from functools import partial
from typing import Self, Literal

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
        self['min_height'] = height

    def set_minimum_width(self, width: int):
        self['min_width'] = width

    def set_size_policy(self, x_policy, y_policy):
        assert y_policy == x_policy == SizePolicy.MinimumExpanding, 'only expanding size policy supported'
        self['grow_x'] = True
        self['grow_y'] = True

    def set_layout(self, layout: i.Layout):
        raise NotImplementedError

class DynamicComponent(rio.Component):
    builder: ComponentBuilder
    _=KW_ONLY
    revision: int = 0

    def __init__(self, builder: ComponentBuilder, revision: int=0):
        super().__init__()
        self.key = id(self)
        self.builder = builder
        self.revision = revision

    def build(self) -> rio.Component:
        return self.builder.build()

class ComponentBuilder:
    __slots__ = ('component','_kwargs')

    s_component_class : type[rio.Component] = None
    s_forced_kwargs = {}
    s_default_kwargs = {}
    s_dynamic = True

    def __init__(self, *children, **kwargs):
        defaults = {kw:value(kwargs) if callable(value) else value for kw,value in self.s_default_kwargs.items()}
        self._kwargs = defaults | kwargs | self.s_forced_kwargs
        kw_kids = self._kwargs.get('children')
        self.component = None

        if children:
            assert not kw_kids, "multiple values for children"
        if not kw_kids:
            self['children'] = list(children)

    def add_children(self, *children):
        existing_children = set(self['children'])
        self['children'].extend(child for child in children if child not in existing_children)
        
    def with_children(self, *args):
        if not args:
            return self
        builder = self.__class__(**self._kwargs)
        builder.add_children(*args)
        return builder

    def _build_children(self):
        return [ child() if isinstance(child,ComponentBuilder) else child for child in self['children'] ]

    def build(self):
        return self.s_component_class(*self._build_children(),
                               **{k: v for k, v in self._kwargs.items() if k != 'children'})

    def __call__(self):
        self.component = DynamicComponent(self) if self.s_dynamic else self.build()
        return self.component

    def __getitem__(self, item):
        #TODO: handle updates in self.component?
        return self._kwargs[item]

    def __contains__(self,item):
        return item in self._kwargs

    def __setitem__(self, item, value):
        self._kwargs[item] = value
        if self.component:
            self.component.revision = self.component.revision + 1

    def setdefault(self, item, default):
        try:
            value = self[item]
        except KeyError:
            value = self[item] = default
        return value

class Widget(ComponentBuilder, _WidgetMixin, i.Widget):
    __slots__ = ('_layout',)
    
    def __init__(self, *children, **kwargs):
        super().__init__(*children, **kwargs)
        self._layout = None
        
    def set_layout(self, layout: i.Layout):
        self._layout = layout
        
    def _build_children(self):
        return self._layout.with_children(*self['children'])._build_children() if self._layout else super()._build_children()

class Label(Widget, i.Label):
    s_component_class = rio.Text
    s_forced_kwargs = {'selectable': False, 'align_x': 0}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self['children']:
            self['children'] = [self._kwargs.pop('text','')]

    def set_text(self, text: str):
        self['children'] = [text]

class PushButton(Label,i.PushButton):
    s_component_class = rio.Button
    s_forced_kwargs = {}
    def clicked_connect(self, bound_method):
        self['on_press'] = bound_method
    def set_flat(self, flat: bool):
        raise NotImplementedError

class VBoxLayout(Widget, i.VBoxLayout):
    s_component_class = rio.Column
    s_stretch_arg = 'grow_y'

    def add_widget(self, widget, stretch=0, **kwargs):
        assert not kwargs, f'kwargs not supported: {kwargs}'
        if stretch:
            assert stretch in (0,1), 'Only stretch of 0 or 1 is currently supported'
            widget[self.s_stretch_arg]=bool(stretch)
        self['children'].append(widget)

    def add_layout(self, layout, **kwargs):
        assert not kwargs, f'kwargs not supported: {kwargs}'
        self._layout = layout

    def set_spacing(self, spacing: int):
        raise NotImplementedError

    def set_contents_margins(self, *args):
        raise NotImplementedError

class HBoxLayout(VBoxLayout,i.HBoxLayout):
    s_component_class = rio.Row
    s_stretch_arg = 'grow_x'

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
        return self._layout.with_children( *self['children'],
            HBoxLayout(
                PushButton('Accept', on_press=self.on_accept),
                PushButton('Reject', on_press=self.on_reject),
            )
        )._build_children()

    def exec(self):
        title = self.title or 'Dialog'
        app = rio.App(name=title, pages=[rio.ComponentPage(name=title, url_segment='', build=self)])
        self.window = len(webview.windows)
        app.run_in_window(debug_mode=True)
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
    s_dynamic = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'label' not in self._kwargs:
            self['label'] = self['children'].pop(0)
        if 'selected_value' not in self._kwargs:
            self['selected_value'] = None
        if 'value' not in self._kwargs:
            self['value'] = self._kwargs['label']
        self['on_select']=self.on_select
        self._button_group = None

    def set_checked(self, checked: bool):
        self['selected_value'] = self['value'] if checked else None
        if checked and self._button_group:
            self._button_group['selected_value'] = self['value']

    def on_select(self, value):
        if self._button_group:
            self._button_group.on_change(value)

    def __call__(self):
        button = super().__call__()
        if self._button_group:
            self._button_group._buttons.append(button)
        return button

class ButtonGroup(Widget, i.ButtonGroup):
    __slots__ = ('_buttons',)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._buttons = []

    def on_change(self, value):
        self['selected_value'] = value
        for button in self._buttons:
            button.selected_value = value

    def add_button(self, button, id):
        if id < len(self['children']):
            self['children'][id] = button
        else:
            assert len(self['children']) == id
            self['children'].append(button)
        if button['selected_value'] == button['value']:
            self['selected_value'] = button['value']
        button._button_group = self

    def button(self, id: int) -> RadioButton:
        return self['children'][id]

    def checked_id(self):
        #TODO: optimize
        selected = self['selected_value']
        for i, button in enumerate(self['children']):
            if button['value'] == selected:
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
        self['title'] = title

    def set_title(self, title: str):
        self['title'] = title

class LineEdit(Widget, i.LineEdit):
    s_component_class = rio.TextInput
    def set_text(self, text: str):
        self['text'] = text

    def text(self):
        return self['text']

    def text_edited_connect(self, bound_method):
        self['on_change'] = lambda ev: bound_method(ev.text)

    def set_read_only(self, read_only: bool):
        self['is_read_only'] = read_only

    def set_password_mode(self):
        self['is_password'] = True

    def editing_finished_connect(self, bound_method):
        self['on_confirm'] = lambda ev: bound_method(ev.text)

class Separator(Widget, i.Separator):
    s_component_class = rio_components.Separator
    s_forced_kwargs = {}

def separator(horizontal = True) -> Separator:
    return Separator() if horizontal else Separator(orientation='vertical')

class ListItem(Widget, i.ListItem):
    __slots__ = ('_list_widget',)
    s_component_class = rio.SimpleListItem
    s_default_kwargs = dict(key=lambda kwargs:kwargs['text'])
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._list_widget = None

    def row(self):
        if self._list_widget:
            return self._list_widget.row(self)

    def set_selected(self, selected: bool):
        return self._list_widget.set_selected(self, selected)

class FindFlags(Enum):
    MATCH_EXACTLY = ()

MatchExactly = FindFlags.MATCH_EXACTLY

class ListWidget(Widget, i.ListWidget):
    s_component_class = rio.ListView
    s_default_kwargs = dict(selection_mode='single')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_items(self, items: [ListItem|str]):
        for item in items:
            self.add_item(item)

    def clicked_connect(self, bound_method):
        self._on_press = bound_method

    def _handle_on_press(self, item):
        if self._on_press:
            self._on_press(item)

    def add_item(self, item: ListItem|str):
        item = ListItem(text=item) if isinstance(item,str) else item
        item['on_press'] = partial(self._handle_on_press, item)
        item._list_widget = self
        self['children'] = self.setdefault('children',[]) + [item]

    def clear(self):
        self['children'] = []

    def find_items(self, text, flags):
        assert flags == MatchExactly, 'only MatchExactly supported'
        return [item for item in self['children'] if text == item['text']]

    def row(self, item: ListItem) -> int:
        return self['children'].index(item)

    def take_item(self, row: int):
        return self['children'].pop(row)

    def set_selected(self, item: ListItem, selected: bool):
        #TODO: this is called from on-click handler for list item, which is
        # inefficient and duplicates rio built-in functionality
        selected_items = self.setdefault('selected_items',[])
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


class RioTreeItemBase(rio.Component):
    """ same as SimpleTreeItem, but includes tooltip and supports double-click """
    text: str = ''
    on_double_press: rio.EventHandler[[]] = None
    on_press: rio.EventHandler[[]] = None
    on_change: rio.EventHandler[[]] = None
    tooltip: str|None = None
    editable: bool = False
    editing: bool = False
    children: list[Self] = []
    is_expanded: bool = False

    def build_primary_text(self):
        if not self.editing:
            return rio.Text(self.text, justify="left", selectable=False)
        return rio.TextInput(
            self.text,
            justify="left",
            on_confirm=self.handle_edit_confirm
        )

    def build_content(self):
        content = self.build_primary_text()
        if self.tooltip:
            content = rio.Row( content,
                        rio.Tooltip(
                            anchor = content,
                            tip = self.tooltip
                        )
           )
        if self.on_double_press:
            content = rio.PointerEventListener( content,
                on_double_press=self.handle_double_press
            )
        return content

    def handle_double_press(self, ev: rio.PointerEvent):
        if self.editable:
            self.editing=True
        if self.on_double_press:
            self.on_double_press()

    def handle_edit_confirm(self, text):
        assert self.editing
        self.text = text
        if self.on_change:
            self.on_change()

    def build(self):
        return rio.SimpleTreeItem(
            self.build_content(),
            children = self.children,
            is_expanded = self.is_expanded,
            on_press=self.on_press,
        )

class RioTreeItem(RioTreeItemBase):
    def __init__(self, *children,**kwargs):
        super().__init__(children=list(children),**kwargs)

class TreeItem(Widget, i.TreeItem):
    __slots__ = ('handlers',)
    s_component_class = RioTreeItem

    def __init__(self, parent: TreeWidget|TreeItem, *args, **kwargs ):
        super().__init__(*args,**kwargs)
        parent['children'] = parent['children'] + [self]
        self.handlers = parent.handlers
        for name, callback in self.handlers.items():
            self[name.replace('_item_', '_')] = partial(callback, self)

    def child_count(self):
        return len(self['children'])

    def set_expanded(self, expanded: bool):
        self['is_expanded'] = expanded

    def set_text(self, col: int, text: str):
        self['text'] = text

    def set_tool_tip(self, col: int, tooltip: str):
        self['tooltip'] = tooltip

    def build(self):
        print(self['text'], [child['text'] for child in self['children']])
        return super().build()

class RioTreeView(rio.Component):
    """makes item-level callbacks available on the tree level"""
    children: list[rio.Component]
    _=KW_ONLY
    selection_mode: Literal["none", "single", "multiple"] = "none",
    col_count: int = 1
    header_labels: list[str] = ['header']


    def __init__(self,*children,
            selection_mode: Literal["none", "single", "multiple"]='none',
            col_count: int = 1,
            header_labels: list[str] = None,
            **kwargs
        ):
        super().__init__(**kwargs)
        self.children=list(children)
        self.selection_mode=selection_mode
        self.col_count=col_count
        if header_labels:
            self.header_labels=header_labels

    def build(self):
        return rio.TreeView(
            *self.children,
            selection_mode = self.selection_mode
        )

class TreeWidget(Widget, i.TreeWidget):
    __slots__ = ('handlers',)
    s_component_class = RioTreeView
    s_default_kwargs = dict(selection_mode='single')

    def __init__(self, *args, **kwargs):
        super().__init__(*args,**kwargs)
        self.handlers = {}

    def set_column_count(self, col_count: int):
        """Set the number of columns in the tree widget."""
        assert col_count in [1,2], 'col_count must be 1 or 2'
        self['col_count'] = col_count

    def set_header_labels(self, labels: list):
        """Set the header labels for each column."""
        self['header_labels'] = labels

    def top_level_item_count(self) -> int:
        """Return the number of top-level items."""
        return len(self['children'])

    def top_level_item(self, i: int) -> TreeItem:
        """Return the top-level item at index i."""
        return self['children'][i]

    def resize_column_to_contents(self, col: int):
        """Adjust the width of the specified column (placeholder)."""
        pass

    def item_expanded_connect(self, bound_method):
        self.handlers['on_item_expand'] = bound_method

    def item_clicked_connect(self, bound_method):
        #self.handlers['on_item_double_press'] = bound_method
        self.handlers['on_item_press'] = bound_method


    def item_pressed_connect(self, bound_method):
        self.handlers['on_item_press'] = bound_method

    def item_changed_connect(self, bound_method):
        raise NotImplementedError

    def edit_item(self, item: TreeItem, col: int):
        """Start editing the specified item in the given column (placeholder)."""
        #self.component.start_editing(item, col)
        raise NotImplementedError

    def open_persistent_editor(self, item: TreeItem, col: int):
        """Open a persistent editor for the specified item and column (placeholder)."""
        #self.component.open_persistent_editor(item, col)
        raise NotImplementedError

    def add_top_level_item(self, item: TreeItem):
        """Add a top-level item to the tree (helper method)."""
        self['children'].append(item)


