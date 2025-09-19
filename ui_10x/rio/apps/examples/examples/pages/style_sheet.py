from __future__ import annotations

from core_10x.ts_union import TsUnion
from ui_10x.examples.style_sheet import StyleSheet
from ui_10x.rio.component_builder import UserSessionContext
from ui_10x.traitable_editor import TraitableEditor

import rio


@rio.page(
    name='StyleSheet',
    url_segment='ss',
)
class StyleSheetPage(rio.Component):
    def build(self) -> rio.Component:
        session_context = self.session[UserSessionContext]
        if not session_context.traitable_store:
            session_context.traitable_store = TsUnion()
        with session_context.traitable_store:
            return TraitableEditor(
                StyleSheet(),
                _confirm=True
            ).dialog().build(self.session)
