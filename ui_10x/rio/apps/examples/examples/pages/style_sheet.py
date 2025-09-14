from __future__ import annotations
import rio

from ui_10x.traitable_editor import TraitableEditor
from ui_10x.examples.style_sheet import StyleSheet

@rio.page(
    name='StyleSheet',
    url_segment='ss',
)
class StyleSheetPage(rio.Component):
    def build(self) -> rio.Component:
        return TraitableEditor(
            StyleSheet(),
            _confirm=True
        ).dialog().build(self.session)
