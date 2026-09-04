"""Browser coverage for the StyleSheet examples page on Rio."""

from __future__ import annotations

import asyncio
import gc
import sys
from pathlib import Path

import rio.testing.browser_client
from ui_10x.rio.browser_helpers import UI_SETTLE_S
from ui_10x.rio.component_builder import DynamicComponent, UserSessionContext
from ui_10x.utils import UxDialog

import rio

_EXAMPLES_ROOT = Path(__file__).resolve().parents[1] / 'apps' / 'examples'
if str(_EXAMPLES_ROOT) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_ROOT))

from examples.pages.style_sheet import StyleSheetPage  # noqa: E402

from examples import on_session_start  # noqa: E402


async def test_style_sheet_page_renders_wysiwyg() -> None:
    """Examples page: StyleSheet editor shows the WYSIWYG preview line."""
    app = rio.App(name='style_sheet_test', build=StyleSheetPage, on_session_start=on_session_start)
    async with rio.testing.BrowserClient(app) as client:
        await asyncio.sleep(UI_SETTLE_S)
        page = client.get_component(StyleSheetPage)
        try:
            labels = await client.execute_js('[...document.querySelectorAll(".rio-text")].map(el => el.children[0]?.innerText || "")')
            inputs = await client.execute_js('[...document.querySelectorAll(".rio-input-box input")].map(el => el.value)')
            assert 'WYSIWYG' in labels, labels
            assert 'This is how it will look...' in inputs, inputs
        finally:
            dialog = next(dc.builder for dc in client.get_components(DynamicComponent) if isinstance(dc.builder, UxDialog))
            if dialog.cancel_callback:
                dialog.cancel_callback()
            dialog.done(0)
            page.session[UserSessionContext].interactive = None
    gc.collect()
