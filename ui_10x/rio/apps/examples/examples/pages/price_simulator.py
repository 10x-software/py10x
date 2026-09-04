from __future__ import annotations

import rio
from examples import components as comps


@rio.page(
    name='PriceSimulator',
    url_segment='stocks',
)
class PriceSimulatorPage(rio.Component):
    def build(self) -> rio.Component:
        return comps.PriceSimulatorComponent()
