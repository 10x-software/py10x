"""Rio coverage for Dialog sizing: content-driven, uncapped.

A dialog takes its natural (`min-content`) size with a floor of
``Dialog.s_min_width_rem``, and nothing caps it -- oversized dialogs stay
reachable through Rio's overlay scroller. Width therefore comes from *declared*
minimums, never from how much text a widget happens to hold.
"""

from __future__ import annotations

import asyncio

import rio.testing
from ui_10x.rio.browser_helpers import UI_SETTLE_S
from ui_10x.rio.component_builder import DynamicComponent, UserSessionContext, session_context
from ui_10x.rio.widgets import Label
from ui_10x.rio.widgets.dialog import Dialog
from ui_10x.rio.widgets.text_edit import TextEdit
from ui_10x.utils import UxDialog, ux_push_button

import rio


def _label_content(content_min_height: int | None):
    content = Label('content')
    if content_min_height is not None:
        content.set_minimum_height(content_min_height)
    return content


async def _open_dialog_and_measure(content_factory=_label_content, content_min_height: int | None = None):
    """Build a session with a button that opens a Dialog wrapping ``content_factory``'s
    result, click it, and return the dialog element's measured box plus the viewport size.
    """
    dlg: Dialog | None = None
    open_button = None

    def open_dialog():
        nonlocal dlg
        content = content_factory(content_min_height)
        dlg = UxDialog(content, title='Sized dialog', ok='Ok', cancel='')
        dlg.show()

    def on_session_start(session):
        nonlocal open_button
        ctx = UserSessionContext()
        session.attach(ctx)
        with session_context(session):
            open_button = ux_push_button('Open', callback=open_dialog)

    app = rio.App(
        name='dialog_sizing_test',
        build=lambda: DynamicComponent(open_button),
        on_session_start=on_session_start,
    )
    async with rio.testing.BrowserClient(app) as test_client:
        await asyncio.sleep(UI_SETTLE_S)

        open_btn = next(b for b in test_client.get_components(rio.Button) if b.content == 'Open')
        await test_client.execute_js(f'''document.querySelector('[dbg-id="{open_btn._id_}"]').querySelector('rio-pressable-element').click()''')
        await asyncio.sleep(UI_SETTLE_S)
        # Let the dialog finish laying out before measuring it.
        await asyncio.sleep(0.5)

        assert dlg is not None and dlg.component is not None, 'dialog did not open'
        dbg_id = dlg.component._id_
        box = await test_client.execute_js(f'''(() => {{
            const el = document.querySelector('[dbg-id="{dbg_id}"]');
            if (!el) return null;
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            const scroller = document.querySelector('.rio-popup-manager-scroller');
            return {{
                w: r.width, h: r.height,
                vw: window.innerWidth, vh: window.innerHeight,
                maxWidth: s.maxWidth, maxHeight: s.maxHeight,
                scrollsY: scroller ? scroller.scrollHeight > scroller.clientHeight + 1 : null,
            }};
        }})()''')

        # Close the dialog and drop references so it doesn't leak into the next test.
        ok_button = next(b for b in test_client.get_components(rio.Button) if b.content == 'Ok')
        await test_client.execute_js(f'''document.querySelector('[dbg-id="{ok_button._id_}"]').querySelector('rio-pressable-element').click()''')
        await asyncio.sleep(UI_SETTLE_S)
        test_client.get_component(DynamicComponent).session[UserSessionContext].interactive = None

    if open_button is not None:
        open_button.component = None
        open_button.subcomponent = None
    return box


async def test_dialog_small_content_sizes_to_content() -> None:
    """A dialog smaller than the viewport is left at its natural size."""
    box = await _open_dialog_and_measure(content_min_height=None)
    assert box is not None
    assert box['h'] < box['vh']
    assert box['w'] < box['vw']
    # Nothing caps a dialog any more — natural content size, no max-* in effect.
    assert box['maxHeight'] in ('none', '')
    assert box['maxWidth'] in ('none', '')


async def test_dialog_oversized_content_is_not_capped_but_stays_reachable() -> None:
    """Content taller than the viewport is left oversized rather than clamped.

    Replaces an earlier test that asserted a clamp to 80% of the viewport. The
    dialog deliberately no longer caps itself: Rio's overlay scroller makes an
    oversized dialog fully reachable, so the clamp bought appearance rather than
    correctness, and it cost a JS measure-and-mutate pass after every open.
    """
    box = await _open_dialog_and_measure(content_min_height=4000)
    assert box is not None
    assert box['h'] > box['vh'], 'content taller than the screen should not be shrunk to fit'
    assert box['maxHeight'] in ('none', ''), 'no cap should be applied'
    # The part that actually matters: it can still be scrolled to.
    assert box['scrollsY'] is True


def _textarea(text: str, min_width: int | None = None):
    content = TextEdit()
    content.set_plain_text(text)
    if min_width is not None:
        content.set_minimum_width(min_width)
    return content


def _plain_textarea(_min_height):
    return _textarea('short')


def _wrapping_textarea(_min_height):
    # A MultiLineTextInput wraps within whatever width it's given and never asks
    # its container for more room, so this text must not widen the dialog.
    return _textarea('A single line of text needing far more than a few hundred pixels to avoid wrapping.')


def _wide_declared_textarea(_min_height):
    return _textarea('short', min_width=4000)


async def test_wrapping_text_alone_does_not_widen_the_dialog() -> None:
    """An aligned dialog is sized by `min-content`, which ignores wrapping text.

    This is the behaviour that motivated the whole fit-width mechanism: a
    textarea is a form control, so no amount of text in it makes the browser ask
    for a wider box. Width has to be *declared*.
    """
    plain = await _open_dialog_and_measure(content_factory=_plain_textarea)
    wrapping = await _open_dialog_and_measure(content_factory=_wrapping_textarea)
    assert plain is not None and wrapping is not None
    assert wrapping['w'] == plain['w']


async def test_declared_minimum_width_widens_the_dialog() -> None:
    """A declared minimum is the one thing that does widen it (cf. `fit_width`)."""
    plain = await _open_dialog_and_measure(content_factory=_plain_textarea)
    wide = await _open_dialog_and_measure(content_factory=_wide_declared_textarea)
    assert plain is not None and wide is not None
    assert wide['w'] > plain['w']
