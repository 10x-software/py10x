from __future__ import annotations

from ui_10x.collection_editor import Collection, CollectionEditor
from ui_10x.rio.component_builder import UserSessionContext
from ui_10x.utils import UxDialog

import rio


class CollectionEditorComponent(rio.Component):
    collection_class: type = None

    def build(self) -> rio.Component:
        with self.session[UserSessionContext].traitable_store:
            return UxDialog(
                CollectionEditor(
                    coll=Collection(
                        cls=self.collection_class
                    )
                ).main_widget()
            ).build(self.session)
