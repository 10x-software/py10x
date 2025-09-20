from __future__ import annotations

import rio
import ui_10x.platform_interface as i
from ui_10x.rio.component_builder import Widget


class TextEdit(Widget, i.TextEdit):
    s_component_class = rio.MultiLineTextInput
    def to_plain_text(self) -> str:
        return self['text']
    def set_plain_text(self, text: str):
        self['text'] = text
    def set_read_only(self, readonly: bool):
        self['is_sensitive'] = not readonly

