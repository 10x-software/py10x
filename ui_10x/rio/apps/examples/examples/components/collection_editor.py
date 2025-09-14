from __future__ import annotations
import rio

from ui_10x.utils import UxDialog
from ui_10x.collection_editor import CollectionEditor, Collection

class CollectionEditorComponent(rio.Component):
    collection_class: type = None

    def build(self) -> rio.Component:
        return UxDialog(
            CollectionEditor(
                coll=Collection(
                    cls=self.collection_class
                )
            ).main_widget()
        ).build(self.session)
