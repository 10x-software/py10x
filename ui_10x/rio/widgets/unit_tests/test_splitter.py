"""Splitter layout: proportional panes with fixed-size handles between them.

Measured in a real browser rather than asserted on the component tree, because what
is under test is the rendered geometry -- rio's own `proportions=` cannot express a
fixed-size child, so the split is applied as an explicit size per pane and only the
DOM shows whether that came out right.
"""

import asyncio

import rio.testing.browser_client
from ui_10x.rio.components.splitter import Splitter

import rio

# One entry per Row: its width, and the width of each child (panes and handles alternate).
_MEASURE = '''(() => {
    const rows = [...document.querySelectorAll('.rio-linear-container.rio-row')];
    return rows.map(r => {
        const helper = r.firstElementChild;
        const kids = [...(helper ? helper.firstElementChild.children : [])];
        return {row: Math.round(r.getBoundingClientRect().width),
                kids: kids.map(c => Math.round(c.getBoundingClientRect().width))};
    });
})()'''

# Each pane carries margin=1 on both sides, which is outside its measured share.
_PANE_MARGIN_PX = 32


def _splitter(proportions, labels=('A' * 48, 'B' * 48)):
    return Splitter(
        children=[rio.Text(t, overflow='nowrap') for t in labels],
        direction='horizontal',
        child_proportions=proportions,
    )


async def _measure(proportions, settle=1.2):
    """Render a splitter and return its Row geometry, plus a second reading.

    The second reading catches a relayout loop: pane sizes are derived from the measured
    width, which triggers a rebuild, so a bad derivation oscillates instead of settling.
    """
    app = rio.App(name='splitter_test', build=lambda: _splitter(proportions))
    async with rio.testing.BrowserClient(app) as client:
        await asyncio.sleep(settle)
        first = await client.execute_js(_MEASURE)
        await asyncio.sleep(1.0)
        return first[0], (await client.execute_js(_MEASURE))[0]


async def test_equal_proportions_split_evenly() -> None:
    first, second = await _measure([1.0, 1.0])

    pane_a, handle, pane_b = first['kids']
    assert pane_a == pane_b, f'equal proportions must give equal panes, got {first["kids"]}'
    assert pane_a + handle + pane_b == first['row']
    assert first == second, f'layout must settle, not oscillate: {first} then {second}'


async def test_proportions_are_honored() -> None:
    first, _ = await _measure([3.0, 1.0])

    pane_a, _handle, pane_b = first['kids']
    # Margins sit outside the proportional share, so compare the shares themselves.
    share_a, share_b = pane_a - _PANE_MARGIN_PX, pane_b - _PANE_MARGIN_PX
    assert share_a == 3 * share_b, f'expected 3:1, got {share_a}:{share_b}'


async def test_handle_is_fixed_and_grabbable() -> None:
    """The handle sits outside the split: it keeps its size whatever the panes do.

    Its width is the *hit* box (handle_hit_size), not the thin visible bar -- a 0.25rem
    bar is too small to grab, so the listener's child is the wider invisible box.
    """
    equal, _ = await _measure([1.0, 1.0])
    skewed, _ = await _measure([3.0, 1.0])

    assert equal['kids'][1] == skewed['kids'][1], 'handle width must not follow the proportions'
    assert equal['kids'][1] > 0
    assert equal['kids'][1] >= skewed['kids'][1]


async def test_single_child_has_no_handle() -> None:
    app = rio.App(name='splitter_one', build=lambda: _splitter([1.0], labels=('only',)))
    async with rio.testing.BrowserClient(app) as client:
        await asyncio.sleep(1.2)
        rows = await client.execute_js(_MEASURE)

    assert len(rows[0]['kids']) == 1, f'one child means no handle, got {rows[0]["kids"]}'
