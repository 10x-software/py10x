from __future__ import annotations
import rio

from core_10x.code_samples.person import Person

from .. import components as comps, UserSessionContext

def guard(event: rio.GuardEvent) -> str | None:
    return None if event.session[UserSessionContext].authenticated else "/"

@rio.page(
    name='CollectionEditor',
    url_segment='ce',
    guard=guard,
)
class CollectionEditor(rio.Component):
    def build(self) -> rio.Component:
        return comps.CollectionEditorComponent(collection_class=Person)
