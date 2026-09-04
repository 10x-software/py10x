from __future__ import annotations

from core_10x.ts_union import TsUnion
from ui_10x.examples.style_sheet import StyleSheet
from ui_10x.rio.component_builder import UserSessionContext, session_context
from ui_10x.traitable_editor import TraitableEditor
from ui_10x.utils import UxDialog

import rio


@rio.page(
    name='StyleSheet',
    url_segment='ss',
)
class StyleSheetPage(rio.Component):
    def build(self) -> rio.Component:
        user_ctx = self.session[UserSessionContext]
        if not user_ctx.traitable_store:
            user_ctx.traitable_store = TsUnion()
        with session_context(self.session):
            return UxDialog(TraitableEditor(StyleSheet(), _confirm=True).main_widget())()
