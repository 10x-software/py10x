from __future__ import annotations

import ui_10x.platform_interface as i
import ui_10x.rio.components as rio_components
from ui_10x.rio.component_builder import Widget


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
