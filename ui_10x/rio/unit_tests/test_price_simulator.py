"""Browser coverage for price_simulator on Rio (examples page and desktop ``exec``)."""

from __future__ import annotations

import asyncio
import gc
import sys
from pathlib import Path

import pytest
import rio.testing.browser_client
from core_10x.exec_control import INTERACTIVE
from core_10x.testlib.strict import need
from ui_10x.rio.browser_helpers import UI_SETTLE_S, wait_for_js_truthy
from ui_10x.rio.component_builder import DynamicComponent, UserSessionContext, session_context
from ui_10x.rio.widgets.table import TraitableTableGrid
from ui_10x.utils import UxAsync, UxDialog

import rio


def _yfinance_available() -> bool:
    try:
        import yfinance
        return True
    except ImportError:
        return False


need(_yfinance_available(), 'yfinance not installed (optional `examples` extra)', allow_module_level=True)

from ui_10x.examples.price_simulator import MarketMonitor, MarketSymbol  # noqa: E402

_EXAMPLES_ROOT = Path(__file__).resolve().parents[1] / 'apps' / 'examples'
if str(_EXAMPLES_ROOT) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_ROOT))

from examples.components.price_simulator import (  # noqa: E402
    PriceSimulatorComponent,
    PriceSimulatorDialog,
)

from examples import on_session_start  # noqa: E402

# First simulator tick is ``threading.Timer(3, ...)`` → ``UxAsync.call``; allow headroom for refresh + DOM.
_FIRST_TICK_TIMEOUT_MS = 15_000

_MSFT_IN_DOM_JS = """(() => {
    const texts = [...document.querySelectorAll('.rio-text')]
        .map(el => el.children[0]?.innerText || '');
    return texts.includes('MSFT');
})()"""


def _fake_symbols(cls):
    return [
        MarketSymbol(symbol='MSFT', prev_close=100.0, std=0.1),
        MarketSymbol(symbol='AAPL', prev_close=200.0, std=0.1),
    ]


@pytest.fixture
def fake_symbols(monkeypatch):
    monkeypatch.setattr(MarketMonitor, 'fetch_symbols', classmethod(_fake_symbols))


def _in_session(component: rio.Component, fn):
    with component.session[UserSessionContext]:
        return fn()


def _monitor(dialog) -> MarketMonitor:
    return dialog.open_callback.__self__


def _cancel_timer(mm: MarketMonitor) -> None:
    if mm.timer is not None:
        mm.timer.cancel()
        mm.timer = None


def _release(mm: MarketMonitor, dialog) -> None:
    _cancel_timer(mm)
    UxAsync.s_instances.pop(mm.update_mkt_data, None)
    mm.symbols.clear()
    if mm.table is not None:
        grid = mm.table.subcomponent
        mm.table.entities.clear()
        if grid is not None:
            grid.rows = ()
        mm.table.component = None
        mm.table.subcomponent = None
        mm.table = None
    if dialog is not None:
        dialog.open_callback = None
        dialog.component = None
        dialog.subcomponent = None


async def _wait_for_first_symbol(client, mm: MarketMonitor) -> None:
    """Wait for the live ``threading.Timer`` → ``UxAsync.call`` tick to put MSFT in the grid and DOM."""
    await wait_for_js_truthy(client, _MSFT_IN_DOM_JS, timeout_ms=_FIRST_TICK_TIMEOUT_MS)
    _cancel_timer(mm)
    grid = client.get_component(TraitableTableGrid)
    assert grid.rows[0][0][0] == 'MSFT'
    assert mm.next_item >= 1


async def test_price_simulator_timer_fills_table(fake_symbols) -> None:
    """Examples page: first timer tick shows the ticker (same bar as GuessWord Try)."""
    app = rio.App(name='price_sim_test', build=PriceSimulatorComponent, on_session_start=on_session_start)
    async with rio.testing.BrowserClient(app) as client:
        await asyncio.sleep(UI_SETTLE_S)
        page = client.get_component(PriceSimulatorComponent)
        dialog = page.session[PriceSimulatorDialog]
        mm = _monitor(dialog)
        try:
            assert mm.timer is not None
            await _wait_for_first_symbol(client, mm)
        finally:
            _in_session(page, lambda: _release(mm, dialog))
            page.session[UserSessionContext].interactive = None
    gc.collect()


async def test_price_simulator_desktop_exec_timer_fills_table(fake_symbols) -> None:
    """``price_simulator.__main__``: monitor under INTERACTIVE, then ``Dialog.exec``-style session."""
    with INTERACTIVE():
        mm = MarketMonitor()
        dialog = UxDialog(
            mm.widget(),
            title='Enjoy watching some stocks :-)',
            open_callback=mm.start,
        )

        def on_session_start(session):
            with session_context(session):
                dialog.on_open()

        app = rio.App(
            name='price_sim_desktop_test',
            build=lambda d=dialog: DynamicComponent(d),
            on_session_start=on_session_start,
            default_attachments=[UserSessionContext()],
        )
        async with rio.testing.BrowserClient(app) as client:
            await asyncio.sleep(UI_SETTLE_S)
            root = client.get_component(DynamicComponent)
            try:
                assert mm.timer is not None
                await _wait_for_first_symbol(client, mm)
            finally:
                _in_session(root, lambda: _release(mm, dialog))
                root.session[UserSessionContext].interactive = None
    gc.collect()
