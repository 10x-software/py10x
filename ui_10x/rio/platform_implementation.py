import webview
import ui_10x.platform_interface as i
import rio
import ui_10x.rio.components as rio_components
from ui_10x.platform_interface import TreeItem


def init() -> rio.App:
    pass

class ComponentBuilder:
    s_component_class : type[rio.Component] = None
    s_forced_kwargs = {}
    __slots__ = ('_children','_kwargs')
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

class Widget(ComponentBuilder, i.Widget):
    __slots__ = ('_layout',)
    
    def __init__(self, *children, **kwargs):
        super().__init__(*children, **kwargs)
        self._layout = None
        
    def set_layout(self, layout: i.Layout):
        self._layout = layout

    def set_style_sheet(self, sh: str):
        ... #TODO
        
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

class HBoxLayout(VBoxLayout,i.HBoxLayout):
    s_component_class = rio.Row

class Dialog(Widget,i.Dialog):
    s_component_class = rio.Column
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
    def __init__(self, title, *children, **kwargs):
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

    def text_changed_connect(self, bound_method):
        self._kwargs['on_text_changed'] = bound_method

class Separator(Widget, i.Separator):
    s_component_class = rio_components.Separator
    s_forced_kwargs = {}

def separator(horizontal = True) -> Separator:
    return Separator() if horizontal else Separator(orientation='vertical')

class ListItem(Widget, i.ListItem):
    pass

class ListWidget(Widget, i.ListWidget):
    s_component_class = rio.ListView
    def add_items(self, items):
        self._children.extend(items)

    def clicked_connect(self, bound_method):
        self._kwargs['on_item_clicked'] = bound_method

    def add_item(self, item):
        self._children.append(item)

    def clear(self):
        pass

    def find_items(self, how):
        pass

    def row(self, item: ListItem) -> int:
        pass

    def take_item(self, row: int):
        pass

class TreeWidget(Widget, i.TreeWidget):
    s_component_class = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def set_column_count(self, column_count: int):
        pass

    def set_header_labels(self, labels: list):
        pass

    def top_level_item_count(self) -> int:
        pass

    def top_level_item(self, i: int) -> TreeItem:
        pass

    def resize_column_to_contents(self, col: int):
        pass

    def item_expanded_connect(self, item):
        pass

    def item_clicked_connect(self, bound_method):
        pass

    def item_pressed_connect(self, bound_method):
        pass

    def item_changed_connect(self, bound_method):
        pass

    def edit_item(self, item, col: int):
        pass

    def open_persistent_editor(self, item, col: int):
        pass



