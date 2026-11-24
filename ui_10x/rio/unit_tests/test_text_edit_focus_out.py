"""What TextEditWidget writes back when it loses focus (Qt6: qt6/unit_tests/test_qt_text_edit.py)."""

from __future__ import annotations

import asyncio

import rio.testing
from core_10x.exec_control import BTP, CACHE_ONLY, INTERACTIVE
from core_10x.traitable import RT, T, Traitable, Ui
from ui_10x.rio.testlib.browser_helpers import UI_SETTLE_S, wait_for_js_value, wait_until
from ui_10x.rio.component_builder import DynamicComponent, UserSessionContext, session_context
from ui_10x.traitable_editor import TraitableEditor

import rio


class _Text(Traitable, keep_history = False):
    name: str   = T(T.ID)
    text: str   = RT(Ui.text('Text'))

    def text_get(self) -> str:
        return 'computed'


_TEXTAREA = 'document.querySelector("textarea")'


async def test_text_edit_commits_an_edit_on_focus_out_and_nothing_else() -> None:
    with CACHE_ONLY(), INTERACTIVE():
        obj                             = _Text(name = 'a')
        editor: TraitableEditor | None  = None
        root                            = None

        def on_session_start(session):
            nonlocal editor, root
            ctx             = UserSessionContext()
            ctx.interactive = BTP.current()
            session.attach(ctx)
            with session_context(session):
                editor  = TraitableEditor(obj, _confirm = True)  # .editor() needs a multi-segment package path
                root    = editor.main_widget()

        app = rio.App(
            name                = 'text_edit_focus_out_test',
            build               = lambda: DynamicComponent(root),
            on_session_start    = on_session_start,
        )
        async with rio.testing.BrowserClient(app) as client:
            await wait_for_js_value(client, f'{_TEXTAREA}?.value ?? ""', 'computed')
            await client.execute_js(f'{_TEXTAREA}.focus();')
            await client.execute_js(f'{_TEXTAREA}.blur();')
            await asyncio.sleep(UI_SETTLE_S)
            assert not obj.is_set(obj.trait('text')), 'focus passing through must not pin the computed value'

            await client.execute_js(f'{_TEXTAREA}.focus();')
            await client.execute_js(f'{_TEXTAREA}.value = "typed";')
            await client.execute_js(f'{_TEXTAREA}.dispatchEvent(new Event("input"));')
            await client.execute_js(f'{_TEXTAREA}.blur();')
            await wait_until(lambda: obj.text == 'typed', message = 'the edit to be committed on blur')

            client.get_component(DynamicComponent).session[UserSessionContext].interactive = None

        editor.entity = None
        editor.main_w = None
        for ed in editor.trait_editors.values():
            if ed.widget is not None:
                ed.widget.component     = None
                ed.widget.subcomponent  = None
                ed.widget               = None
        editor.trait_editors.clear()
        editor = root = obj = None
