from __future__ import annotations
import rio

from core_10x.code_samples.person import Person

from .. import components as comps


@rio.page(
    name='CollectionEditor',
    url_segment='',
)
class CollectionEditor(rio.Component):
    def build(self) -> rio.Component:
        return comps.CollectionEditorComponent(collection_class=Person)
