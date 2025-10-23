from __future__ import annotations

import rio
import ui_10x.platform_interface as i
from ui_10x.rio.component_builder import Widget


class TextEdit(Widget, i.TextEdit):
    s_component_class = rio.MultiLineTextInput

    def _make_kwargs(self, **kwargs):
        kw = super()._make_kwargs(**kwargs)
        handler = self.focus_out_event
        if handler.__func__ != TextEdit.focus_out_event:  # do not set unless implemented
            kw['on_lose_focus'] = self.callback(handler)
        # TODO: test clipboard interactions
        return kw

    def to_plain_text(self) -> str:
        return self['text']

    def set_plain_text(self, text: str):
        self['text'] = text

    def set_read_only(self, readonly: bool):
        self['is_sensitive'] = not readonly

    def focus_out_event(self, event): ...
