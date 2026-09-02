"""Browser coverage for guess-word on Rio (examples page and desktop ``exec``)."""

from __future__ import annotations

import asyncio
import gc
import sys
from pathlib import Path

import pytest
import rio.testing.browser_client
from core_10x.exec_control import INTERACTIVE
from ui_10x.examples import guess_word as gw
from ui_10x.examples.guess_word import _GuessWordData
from ui_10x.rio.browser_helpers import (
    UI_SETTLE_S,
    click_client_button,
    ui_settle,
    wait_for_js_truthy,
    wait_for_js_value,
    wait_for_line_edit_value,
    wait_for_pressable_sensitive,
    wait_for_rio_refresh,
    wait_until,
)
from ui_10x.rio.component_builder import DynamicComponent, UserSessionContext
from ui_10x.rio.widgets.table import TraitableTableGrid

import rio

_EXAMPLES_ROOT = Path(__file__).resolve().parents[1] / 'apps' / 'examples'
if str(_EXAMPLES_ROOT) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_ROOT))

from examples.components.guess_word import GuessWordComponent, GuessWordSession, guess_word_dialog  # noqa: E402

from examples import on_session_start  # noqa: E402

LINE_EDIT_INPUT = '.rio-input-box input'

_CELL_LETTERS_JS = """(() => {{
    const cells = [...document.querySelectorAll('.rio-rectangle .rio-text')]
        .map(el => (el.children[0]?.innerText || '').replace(/\\u00a0/g, '').trim())
        .filter(t => t.length === 1);
    return cells.slice(0, {n}).join('');
}})()"""


@pytest.fixture
def silence_message_boxes(monkeypatch):
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(gw, 'ux_warning', lambda text, *a, **k: calls.append(('warn', text)))
    monkeypatch.setattr(gw, 'ux_success', lambda text, *a, **k: calls.append(('ok', text)))
    return calls


def _in_session(component: rio.Component, fn):
    with component.session[UserSessionContext]:
        return fn()


def _release_game(game, root) -> None:
    te = game.top_editor
    for ed in te.trait_editors.values():
        w = ed.widget
        if w is not None:
            if 'on_press' in getattr(w, '_kwargs', {}):
                w['on_press'] = None
            w.component = None
            w.subcomponent = None
            ed.widget = None
    te.trait_editors.clear()
    te.entity = None
    te.main_w = None

    table = game.table
    table.entities.clear()
    table.component = None
    table.subcomponent = None

    if getattr(game, 'layout', None) is not None:
        game.layout = None
    if root is not None:
        if getattr(root, 'open_callback', None) is not None:
            root.open_callback = None
        root.component = None
        root.subcomponent = None
        if getattr(root, '_layout', None) is not None:
            root._layout = None


async def _type_blur_try(client, game, session_owner) -> tuple[str, int]:
    count, num_chars, secret = _in_session(session_owner, lambda: (game.count, game.num_chars, game.the_word))
    await wait_for_js_truthy(
        client,
        f'document.querySelectorAll(".rio-rectangle").length >= {count * num_chars}',
    )
    pool = _GuessWordData.noun_pool()[num_chars]
    guess = next(w for w in pool if w.upper() != secret).upper()

    await client._page.click(LINE_EDIT_INPUT)
    await client._page.keyboard.type(guess)
    await ui_settle()
    await wait_for_line_edit_value(client, guess)
    await client.execute_js('document.querySelector(".rio-input-box input").blur();')
    await wait_until(
        lambda: _in_session(session_owner, lambda: game.guess == guess),
        message='guess committed on lost focus',
    )
    try_btn = next(b for b in client.get_components(rio.Button) if b.content == 'Try')
    await wait_for_pressable_sensitive(client, True)
    await click_client_button(client, try_btn)
    await wait_for_rio_refresh(client)
    await ui_settle()
    return guess, num_chars


async def test_guess_word_try_renders_letters_in_cells(silence_message_boxes) -> None:
    """Examples page: type, blur, Try — first row shows the guess."""
    app = rio.App(name='guess_word_test', build=GuessWordComponent, on_session_start=on_session_start)
    async with rio.testing.BrowserClient(app) as client:
        await asyncio.sleep(UI_SETTLE_S)
        page = client.get_component(GuessWordComponent)
        bag = GuessWordSession.of(page.session)
        game = bag.game
        guess, n = await _type_blur_try(client, game, page)
        try:
            assert not [c for c in silence_message_boxes if c[0] == 'warn'], silence_message_boxes
            grid = client.get_component(TraitableTableGrid)
            assert ''.join(cell[0] for cell in grid.rows[0]) == guess
            await wait_for_js_value(client, _CELL_LETTERS_JS.format(n=n), guess)
        finally:
            _in_session(page, lambda: _release_game(game, bag.dialog))
            bag.game = None
            bag.dialog = None
    gc.collect()


async def test_guess_word_desktop_exec_shape(silence_message_boxes) -> None:
    """``guess_word.__main__``: Game under INTERACTIVE, then ``Dialog.exec``-style session."""
    with INTERACTIVE():
        game, dialog = guess_word_dialog()

        def on_session_start(session):
            with session[UserSessionContext]:
                dialog.on_open()

        app = rio.App(
            name='guess_word_desktop_test',
            build=lambda d=dialog: DynamicComponent(d),
            on_session_start=on_session_start,
            default_attachments=[UserSessionContext()],
        )
        async with rio.testing.BrowserClient(app) as client:
            await asyncio.sleep(UI_SETTLE_S)
            root = client.get_component(DynamicComponent)
            guess, n = await _type_blur_try(client, game, root)
            try:
                assert not [c for c in silence_message_boxes if c[0] == 'warn'], silence_message_boxes
                grid = client.get_component(TraitableTableGrid)
                assert ''.join(cell[0] for cell in grid.rows[0]) == guess
                await wait_for_js_value(client, _CELL_LETTERS_JS.format(n=n), guess)
            finally:
                _in_session(root, lambda: _release_game(game, dialog))
                _release_game(game, dialog)
                root.session[UserSessionContext].interactive = None
    gc.collect()
