from __future__ import annotations

import rio
import ui_10x.platform_interface as i
import ui_10x.rio.components as rio_components
from ui_10x.rio.component_builder import Widget


class RadioButton(Widget, i.RadioButton):
    __slots__ = '_button_group'
    s_component_class = rio_components.RadioButton
    s_dynamic = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'label' not in self._kwargs:
            self['label'] = self.get_children().pop(0)
        if 'selected_value' not in self._kwargs:
            self['selected_value'] = None
        if 'value' not in self._kwargs:
            self['value'] = self._kwargs['label']
        self['on_select'] = self.on_select
        self._button_group = None

    def set_checked(self, checked: bool):
        self['selected_value'] = self['value'] if checked else None
        if checked and self._button_group:
            self._button_group['selected_value'] = self['value']

    def on_select(self, value):
        if self._button_group:
            self._button_group.on_change(value)

    def __call__(self, session: rio.Session) -> rio.Component:
        button = super().__call__(session)
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
        if id < len(self.get_children()):
            self.get_children()[id] = button
        else:
            assert len(self.get_children()) == id
            self.get_children().append(button)
        if button['selected_value'] == button['value']:
            self['selected_value'] = button['value']
        button._button_group = self

    def button(self, id: int) -> RadioButton:
        return self.get_children()[id]

    def checked_id(self):
        # TODO: optimize
        selected = self['selected_value']
        for idx, button in enumerate(self.get_children()):
            if button['value'] == selected:
                return idx
        return -1
