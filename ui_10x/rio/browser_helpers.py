"""Condition-based waits for Rio BrowserClient tests.

Prefer ``asyncio.sleep(UI_SETTLE_S)`` between browser actions — it is faster on
local runners and gives Rio time to finish the Python↔browser round trip.  Use the
``wait_for_*`` helpers only where a fixed delay is known to flake on slow CI
(e.g. ``wait_for_input_values`` after opening the collection-editor dialog).
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

import rio

UI_SETTLE_S = 0.5


async def ui_settle() -> None:
    """Short pause for Rio's async Python↔browser context to settle."""
    await asyncio.sleep(UI_SETTLE_S)

DEFAULT_DOM_TIMEOUT_MS = 10_000
DEFAULT_POLL_TIMEOUT_S = 10.0

LABEL_CLIENT_TEXT_JS = 'document.querySelector(".rio-text")?.children[0]?.innerText || ""'
BUTTON_CLIENT_TEXT_JS = 'document.querySelector(".rio-button .rio-text")?.children[0]?.innerText || ""'
CHECKBOX_JS = 'document.querySelector("input[type=\'checkbox\']")'
LINE_EDIT_INPUT_JS = 'document.querySelector(".rio-input-box input")'
LINE_EDIT_TOOLTIP_TEXT_JS = (
    'document.querySelector(".rio-tooltip-popup .rio-text")?.children[0]?.innerText || ""'
)
CALENDAR_SELECTED_DATE_JS = (
    'document.querySelector(".rio-calendar-selected-day")?.textContent + " " + '
    'document.querySelector(".rio-calendar-year-month-display")?.textContent'
)
LIST_ITEMS_COUNT_JS = 'document.querySelectorAll(".rio-selectable-item").length'
LIST_SELECTED_TEXT_JS = (
    'document.querySelector(".selected .rio-text")?.children[0]?.innerText || ""'
)
GROUP_BOX_COLUMN_TEXT_COUNT_JS = 'document.querySelectorAll(".rio-column .rio-text").length'
GROUP_BOX_BUTTON_COUNT_JS = 'document.querySelectorAll(".rio-button").length'


def _js_literal(value: Any) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        return repr(value)
    return str(value)


async def wait_for_js_value(
    test_client,
    expression: str,
    expected: Any,
    *,
    timeout_ms: int = DEFAULT_DOM_TIMEOUT_MS,
) -> None:
    """Wait until a JS expression equals the expected value."""
    await test_client.playwright_page.wait_for_function(
        f'() => ({expression}) === {_js_literal(expected)}',
        timeout=timeout_ms,
    )


async def wait_for_js_truthy(
    test_client,
    expression: str,
    *,
    timeout_ms: int = DEFAULT_DOM_TIMEOUT_MS,
) -> None:
    """Wait until a JS expression evaluates to a truthy value."""
    await test_client.playwright_page.wait_for_function(
        f'() => !!({expression})',
        timeout=timeout_ms,
    )


async def wait_for_rio_refresh(test_client, *, timeout_s: float = 2.0) -> None:
    """Wait for the next Rio refresh, but do not block forever if none arrives."""
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(test_client.wait_for_refresh(), timeout=timeout_s)


async def wait_until(
    predicate: Callable[[], bool | Awaitable[bool]],
    *,
    timeout_s: float = DEFAULT_POLL_TIMEOUT_S,
    interval_s: float = 0.05,
    message: str = 'condition not met',
) -> None:
    """Poll a Python predicate until it returns true or timeout."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        result = predicate()
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            return
        await asyncio.sleep(interval_s)
    raise AssertionError(f'{message} within {timeout_s}s')


async def wait_for_label_client_text(
    test_client,
    text: str,
    *,
    timeout_ms: int = DEFAULT_DOM_TIMEOUT_MS,
) -> None:
    await wait_for_js_value(test_client, LABEL_CLIENT_TEXT_JS, text, timeout_ms=timeout_ms)


async def wait_for_button_client_text(
    test_client,
    text: str,
    *,
    timeout_ms: int = DEFAULT_DOM_TIMEOUT_MS,
) -> None:
    await wait_for_js_value(test_client, BUTTON_CLIENT_TEXT_JS, text, timeout_ms=timeout_ms)


async def wait_for_button_interactive(
    test_client,
    text: str | None = None,
    *,
    timeout_ms: int = DEFAULT_DOM_TIMEOUT_MS,
) -> None:
    """Wait until a Rio button is painted and ready to receive clicks."""
    if text is not None:
        await wait_for_button_client_text(test_client, text, timeout_ms=timeout_ms)
    await test_client.playwright_page.wait_for_function(
        '''() => {
            const el = document.querySelector(".rio-button");
            if (!el) return false;
            const r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0;
        }''',
        timeout=timeout_ms,
    )
    await test_client.execute_js(
        'new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))'
    )


async def wait_for_checkbox_state(
    test_client,
    *,
    checked: bool | None = None,
    disabled: bool | None = None,
    timeout_ms: int = DEFAULT_DOM_TIMEOUT_MS,
) -> None:
    if checked is not None:
        await wait_for_js_value(test_client, f'{CHECKBOX_JS}.checked', checked, timeout_ms=timeout_ms)
    if disabled is not None:
        await wait_for_js_value(test_client, f'{CHECKBOX_JS}.disabled', disabled, timeout_ms=timeout_ms)


async def wait_for_line_edit_value(
    test_client,
    value: str,
    *,
    timeout_ms: int = DEFAULT_DOM_TIMEOUT_MS,
) -> None:
    await wait_for_js_value(test_client, f'{LINE_EDIT_INPUT_JS}.value', value, timeout_ms=timeout_ms)


async def wait_for_line_edit_disabled(
    test_client,
    disabled: bool,
    *,
    timeout_ms: int = DEFAULT_DOM_TIMEOUT_MS,
) -> None:
    await wait_for_js_value(test_client, f'{LINE_EDIT_INPUT_JS}.disabled', disabled, timeout_ms=timeout_ms)


async def wait_for_line_edit_type(
    test_client,
    input_type: str,
    *,
    timeout_ms: int = DEFAULT_DOM_TIMEOUT_MS,
) -> None:
    await wait_for_js_value(test_client, f'{LINE_EDIT_INPUT_JS}.type', input_type, timeout_ms=timeout_ms)


async def wait_for_line_edit_tooltip(
    test_client,
    text: str,
    *,
    timeout_ms: int = DEFAULT_DOM_TIMEOUT_MS,
) -> None:
    await wait_for_js_value(test_client, LINE_EDIT_TOOLTIP_TEXT_JS, text, timeout_ms=timeout_ms)


async def wait_for_calendar_client_date(
    test_client,
    expected: date,
    *,
    timeout_s: float = DEFAULT_POLL_TIMEOUT_S,
) -> None:
    import dateutil.parser

    async def matches() -> bool:
        selected_date = await test_client.execute_js(CALENDAR_SELECTED_DATE_JS)
        return dateutil.parser.parse(selected_date).date() == expected

    await wait_until(matches, timeout_s=timeout_s, message=f'calendar to show {expected}')


async def wait_for_list_item_count(
    test_client,
    count: int,
    *,
    timeout_ms: int = DEFAULT_DOM_TIMEOUT_MS,
) -> None:
    await wait_for_js_value(test_client, LIST_ITEMS_COUNT_JS, count, timeout_ms=timeout_ms)


async def wait_for_list_selection(
    test_client,
    text: str,
    *,
    timeout_ms: int = DEFAULT_DOM_TIMEOUT_MS,
) -> None:
    await wait_for_js_value(test_client, LIST_SELECTED_TEXT_JS, text, timeout_ms=timeout_ms)


async def wait_for_group_box_counts(
    test_client,
    *,
    text_count: int,
    button_count: int,
    timeout_ms: int = DEFAULT_DOM_TIMEOUT_MS,
) -> None:
    await wait_for_js_value(test_client, GROUP_BOX_COLUMN_TEXT_COUNT_JS, text_count, timeout_ms=timeout_ms)
    await wait_for_js_value(test_client, GROUP_BOX_BUTTON_COUNT_JS, button_count, timeout_ms=timeout_ms)


async def wait_for_group_box_column_text(
    test_client,
    index: int,
    text: str,
    *,
    timeout_ms: int = DEFAULT_DOM_TIMEOUT_MS,
) -> None:
    await wait_for_js_value(
        test_client,
        f'document.querySelectorAll(".rio-column .rio-text")[{index}]?.innerText || ""',
        text,
        timeout_ms=timeout_ms,
    )


async def wait_for_weight_unit_pairs(
    test_client,
    weight: str,
    unit: str,
    *,
    min_pairs: int = 1,
    timeout_ms: int = DEFAULT_DOM_TIMEOUT_MS,
) -> None:
    await test_client.playwright_page.wait_for_function(
        f'''() => {{
            const inputs = [...document.querySelectorAll("input")];
            let pairs = 0;
            for (let i = 0; i < inputs.length - 1; i++) {{
                if (inputs[i].value === {weight!r} && inputs[i + 1].value === {unit!r}) {{
                    pairs += 1;
                }}
            }}
            return pairs >= {min_pairs};
        }}''',
        timeout=timeout_ms,
    )


async def wait_for_input_values(
    test_client,
    *,
    weight_index: int,
    weight: str,
    unit_index: int,
    unit: str,
    timeout_ms: int = DEFAULT_DOM_TIMEOUT_MS,
) -> None:
    await test_client.playwright_page.wait_for_function(
        f'''() => {{
            const inputs = document.querySelectorAll("input");
            return inputs[{weight_index}]?.value === {weight!r}
                && inputs[{unit_index}]?.value === {unit!r};
        }}''',
        timeout=timeout_ms,
    )


async def press_rio_button(test_client, button) -> None:
    """Click a Rio button via its pressable element (for complex layouts)."""
    await test_client.execute_js(
        f'''document.querySelector('[dbg-id="{button._id_}"]')'''
        f'''.querySelector('rio-pressable-element').click()'''
    )


async def click_client_button(test_client, button=None) -> None:
    """Simulate a user mouse click at the center of a Rio button.

    Uses real mouse coordinates so disabled buttons correctly ignore clicks.
    Do not use ``click_component`` for disabled-interaction tests — it calls
    the Python handler directly and bypasses the disabled state.
    """
    if button is None:
        button = test_client.get_component(rio.Button)
    rect = await test_client.execute_js(
        f'''() => {{
            const el = document.querySelector('[dbg-id="{button._id_}"]');
            const r = el.getBoundingClientRect();
            return {{x: r.left + r.width / 2, y: r.top + r.height / 2}};
        }}'''
    )
    await test_client.click(rect['x'], rect['y'])
    await wait_for_rio_refresh(test_client)


async def click_rio_button(test_client, button) -> None:
    """Alias for :func:`press_rio_button`."""
    await press_rio_button(test_client, button)
