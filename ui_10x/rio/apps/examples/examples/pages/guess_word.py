from __future__ import annotations

import rio
from examples import components as comps


@rio.page(
    name='GuessWord',
    url_segment='guess',
)
class GuessWordPage(rio.Component):
    def build(self) -> rio.Component:
        return comps.GuessWordComponent()
