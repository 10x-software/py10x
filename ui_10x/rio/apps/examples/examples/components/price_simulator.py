from __future__ import annotations

from ui_10x.examples.price_simulator import MarketMonitor
from ui_10x.rio.component_builder import session_context
from ui_10x.utils import UxDialog

import rio


class PriceSimulatorDialog(UxDialog): ...


class PriceSimulatorComponent(rio.Component):
    def build(self) -> rio.Component:
        try:
            dialog = self.session[PriceSimulatorDialog]
        except KeyError:
            with session_context(self.session):
                mm = MarketMonitor()
                dialog = PriceSimulatorDialog(
                    mm.widget(),
                    title='Enjoy watching some stocks :-)',
                    ok='',
                    cancel='',
                    open_callback=mm.start,
                )
                self.session.attach(dialog)
                dialog.on_open()
        return dialog()
