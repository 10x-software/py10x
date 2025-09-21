from __future__ import annotations

from core_10x.code_samples.person import Person

import rio

from .. import UserSessionContext
from .. import components as comps


def guard(event: rio.GuardEvent) -> str | None:
    return None if event.session[UserSessionContext].authenticated else '/'


@rio.page(
    name='CollectionEditor',
    url_segment='ce',
    guard=guard,
)
class CollectionEditor(rio.Component):
    def build(self) -> rio.Component:
        return comps.CollectionEditorComponent(collection_class=Person)
