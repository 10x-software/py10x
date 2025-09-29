from __future__ import annotations

import ui_10x.platform_interface as i
import ui_10x.rio.components as rio_components
from ui_10x.rio.component_builder import Widget


class RadioButton(Widget, i.RadioButton):
    __slots__ = '_button_group'
    s_component_class = rio_components.RadioButton

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'label' not in self._kwargs:
            self['label'] = self.get_children().pop(0)
        if 'value' not in self._kwargs:
            self['value'] = self._kwargs['label']
        self['on_select'] = self.on_select
        self['checked'] = False
        self._button_group = None

    def set_checked(self, checked: bool):
        self['checked'] = checked
        if self._button_group:
            self._button_group.on_change(self)

    def on_select(self):
        self.set_checked(not self['checked'])


class ButtonGroup(Widget, i.ButtonGroup):
    s_component_class = rio_components.GroupBox
    s_pass_children_in_kwargs = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def on_change(self, changed_button: RadioButton):
        if changed_button['checked']:
            for child in self.get_children():
                if child is not changed_button:
                    child['checked'] = False

    def add_button(self, button, id):
        if id < len(self.get_children()):
            self.get_children()[id] = button
        else:
            assert len(self.get_children()) == id
            self.get_children().append(button)
        button._button_group = self

    def button(self, id: int) -> RadioButton:
        return self.get_children()[id]

    def checked_id(self):
        # TODO: optimize
        for idx, button in enumerate(self.get_children()):
            if button['checked']:
                return idx
        return -1
