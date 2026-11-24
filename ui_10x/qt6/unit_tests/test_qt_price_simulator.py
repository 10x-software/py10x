"""Qt6 counterpart of rio/unit_tests/test_price_simulator.py: the desktop ``exec`` shape (Rio's examples page has no Qt analog)."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt

from core_10x.exec_control import INTERACTIVE
from ui_10x.examples.price_simulator import MarketMonitor, MarketSymbol
from ui_10x.qt6.testlib import qt_helpers as h
from ui_10x.utils import UxDialog

#-- the first tick is threading.Timer(3, ...) -> UxAsync.call, a signal queued to the UI thread
_FIRST_TICK_TIMEOUT_S = 15


@pytest.fixture
def fake_symbols(monkeypatch):
    def symbols(cls):
        return [MarketSymbol(symbol = 'MSFT', prev_close = 100.0, std = 0.1), MarketSymbol(symbol = 'AAPL', prev_close = 200.0, std = 0.1)]

    monkeypatch.setattr(MarketMonitor, 'fetch_symbols', classmethod(symbols))


def _stop(mm) -> None:
    """Each update, run on the UI thread, starts the next timer: cancel until a pending one starts no more."""
    while (timer := mm.timer) is not None:
        mm.timer = None
        timer.cancel()
        timer.join()
        h.app().processEvents()


def test_price_simulator_desktop_exec_timer_fills_table(fake_symbols) -> None:
    """``price_simulator.__main__``: the monitor under INTERACTIVE in an exec()'d dialog; the first tick lists MSFT."""
    with INTERACTIVE():
        mm      = MarketMonitor()
        dialog  = UxDialog(mm.widget(), title = 'Enjoy watching some stocks :-)', open_callback = mm.start)

        def watch(d):
            assert mm.timer is not None
            model = mm.table.model()
            h.wait_until(lambda: model.rowCount() >= 1, timeout_s = _FIRST_TICK_TIMEOUT_S, message = 'the first timer tick')
            _stop(mm)
            assert model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole) == 'MSFT'
            assert mm.next_item >= 1
            h.click(h.button(d, 'Cancel'))

        try:
            h.run_modal(dialog.exec, watch, timeout_s = _FIRST_TICK_TIMEOUT_S + 5)
        finally:
            _stop(mm)
            mm.symbols.clear()
