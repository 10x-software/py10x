from __future__ import annotations

import ui_10x.platform_interface as i
import ui_10x.rio.components as rio_components
from ui_10x.rio.component_builder import Widget


class CheckBox(Widget, i.CheckBox):
    s_component_class = rio_components.LabeledCheckBox

    def set_checked(self, checked: bool):
        self["is_on"] = checked

    def is_checked(self) -> bool:
        return self["is_on"]

    def state_changed_connect(self, bound_method):
        def state_change_handler(event):
            bound_method(event.is_on)
        self["on_change"] = self.callback(state_change_handler)

    def set_text(self, text: str):
        self["label"] = text