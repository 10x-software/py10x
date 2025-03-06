import dataclasses
import threading
from functools import partial

import webview
import ui_10x.platform_interface as i
import rio
import ui_10x.rio.components as rio_components


def init() -> rio.App:
    pass

class ComponentBuilder:
    s_component_class : type[rio.Component] = None
    s_forced_kwargs = {}
    __slots__ = ('_args','_kwargs')
    def __init__(self, *args, **kwargs):
        self._args = list(args)
        self._kwargs = kwargs | self.s_forced_kwargs

    def _build_children(self):
        return [ arg() if isinstance(arg,ComponentBuilder) else arg for arg in self._args ]

    def __call__(self):
        return self.s_component_class(*self._build_children(), **self._kwargs)

class Widget(ComponentBuilder, i.Widget):
    __slots__ = ('_layout',)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._layout = None
        
    def set_layout(self, layout: i.Layout):
        self._layout = layout

    def set_style_sheet(self, sh: str):
        ... #TODO
        
    def _build_children(self):
        children = super()._build_children()
        return self._layout(*children) if self._layout else children

class Label(Widget, i.Label):
    s_component_class = rio.Text
    s_forced_kwargs = {'selectable': False, 'align_x': 0}
    def set_text(self, text: str):
        self._kwargs['content'] = text

class PushButton(Label,i.PushButton):
    s_component_class = rio.Button
    s_forced_kwargs = {}
    def clicked_connect(self, bound_method):
        self._kwargs['on_press'] = bound_method
    def set_flat(self, flat: bool):
        ... #TODO

class VBoxLayout(Widget, i.VBoxLayout):
    s_component_class = rio.Column

    def add_widget(self, widget, **kwargs):
        assert not kwargs
        self._args.append(widget)

    def add_layout(self, layout):
        #probably wrong...
        self._args.append(layout)

class HBoxLayout(VBoxLayout,i.HBoxLayout):
    s_component_class = rio.Row

class Dialog(Widget,i.Dialog):
    s_component_class = rio.Column
    def __init__(self, *args, on_accept=None, on_reject=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_accept = self._wrapper(on_accept, accept=True)
        self.on_reject = self._wrapper(on_reject)
        self.window = None
        self.accepted = True
        self._layout = VBoxLayout

    def set_window_title(self, title: str):
        self._kwargs['title'] = title

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

    def __call__(self):
        return self._layout(
            *self._args,
            HBoxLayout(
                PushButton('Accept', on_press=self.on_accept),
                PushButton('Reject', on_press=self.on_reject),
            )
        )()

    def exec(self):
        title = self._kwargs.get('title','Dialog')
        app = rio.App(name=title, pages=[rio.ComponentPage(name=title, url_segment='', build=self)])
        self.window = len(webview.windows)
        app.run_in_window()
        return self.accepted

class RadioButton(Widget, i.RadioButton):
    s_component_class = rio_components.RadioButton

    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'label' not in self._kwargs:
            self._kwargs['label'] = self._args.pop(0)
        if 'selected_value' not in self._kwargs:
            self._kwargs['selected_value'] = None
        if 'value' not in self._kwargs:
            self._kwargs['value'] = self._kwargs['label']

    def set_checked(self, checked: bool):
        self._kwargs['selected_value'] = self._kwargs['value'] if checked else None

class ButtonGroup(Widget, i.ButtonGroup):
    s_component_class = rio_components.RadioButtons
    def add_button(self, button, id):
        if id < len(self._args):
            self._args[id] = button
        else:
            assert len(self._args) == id
            self._args.append(button)

    def button(self, id: int) -> RadioButton:
        return self._args[id]

    def checked_id(self):
        #TODO: optimize
        selected = self._kwargs['selected_value']
        for i, button in enumerate(self._args):
            if button._kwargs['value'] == selected:
                return i
        return -1


class GroupBox(Widget, i.GroupBox):
    s_component_class = rio_components.GroupBox
    def set_title(self, title: str):
        self._kwargs['title'] = title

    def set_layout(self, layout):
        #probably wrong...
        self._args.append(layout)


class LineEdit(Widget, i.LineEdit):
    s_component_class = rio.TextInput
    def set_text(self, text: str):
        self._kwargs['text'] = text

    def text(self):
        return self._kwargs['text']

    def text_changed_connect(self, bound_method):
        self._kwargs['on_text_changed'] = bound_method

class Separator(Label, i.Label):
    s_component_class = rio_components.Separator
    s_forced_kwargs = {}

def separator(horizontal = True) -> Label:
    return Separator() if horizontal else Separator(orientation='vertical')