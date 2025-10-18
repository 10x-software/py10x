from __future__ import annotations

import ui_10x.platform_interface as i
import ui_10x.rio.components as rio_components
from ui_10x.rio.component_builder import MouseEvent, Widget


class LineEdit(Widget, i.LineEdit):
    s_default_kwargs = dict(text='')
    s_component_class = rio_components.LineEditComponent
    s_single_child = True
    s_children_attr = 'text'

    def set_text(self, text: str):
        self['text'] = text or ''

    def text(self):
        return self['text']

    def text_edited_connect(self, bound_method):
        self['on_change'] = self.callback(lambda ev: bound_method(ev.text))

    def set_password_mode(self):
        self['is_secret'] = True

    def editing_finished_connect(self, bound_method):
        self['on_lose_focus'] = self.callback(lambda ev: bound_method())

    def _make_kwargs(self, **kwargs):
        kw = super()._make_kwargs(**kwargs)
        handler = self.mouse_press_event
        if handler.__func__ != LineEdit.mouse_press_event:  # do not set unless re-implemented
            kw['on_pointer_up'] = self.callback(lambda event: handler(MouseEvent(event)))
        return kw

    def mouse_press_event(self, event: i.MouseEvent):
        pass
