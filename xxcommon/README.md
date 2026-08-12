# `xxcommon`

Shared, finance-oriented building blocks layered on top of `core_10x`:

- **`xxcalendar`** — `Calendar` with non-working days, set algebra (union / intersection), and adjustments.
- **`rdate`** — `RDate` tenors (e.g. `'3M'`, `'1Y'`) with business-day roll rules and date schedules.
- **`curve`** — `Curve` / `DateCurve` with pluggable interpolation (`scipy.interpolate`).
- **`event` / `event_processor`** — `Event`, a timestamped append-only record, and `EventProcessor`, a watermark-tracked, class-dispatched consumer of one or more `Event` subclasses.

For the broader project (concepts, install, tests, style), see [`README.md`](../README.md), [`INSTALLATION.md`](../INSTALLATION.md), [`GETTING_STARTED.md`](../GETTING_STARTED.md), and [`CONTRIBUTING.md`](../CONTRIBUTING.md) at the repository root.

> Code blocks below are executable as documentation tests — `Calendar` has stored traits, so calendar examples are wrapped in `with CACHE_ONLY():` per the *Why Storage Context is Required* section in `GETTING_STARTED.md`.

---

## `RDate` — relative dates / tenors

An `RDate` is a `(count, freq)` pair describing an offset like *3 months* or *5 business days*. It can be constructed from a symbol string or from explicit parts.

### Construction

```python
from xxcommon.rdate import RDate, TENOR_FREQUENCY

RDate('3M')                                       # 3 months
RDate('1Y')                                       # 1 year
RDate('-2Q')                                      # -2 quarters
RDate(freq=TENOR_FREQUENCY.MONTH, count=3)        # same as RDate('3M')
RDate(freq=TENOR_FREQUENCY.YEAR)                  # count defaults to 1
```

Supported frequency characters (see `FREQUENCY_TABLE` in `xxcommon/rdate.py`):

| Char  | `TENOR_FREQUENCY` | Meaning           |
|-------|-------------------|-------------------|
| `B`   | `BIZDAY`          | Business days     |
| `C`   | `CALDAY`          | Calendar days     |
| `W`   | `WEEK`            | Weeks             |
| `M`   | `MONTH`           | Months            |
| `Q`   | `QUARTER`         | Quarters (3M)     |
| `S`   | `HALF_YEAR`       | Half-years (6M)   |
| `Y`   | `YEAR`            | Years             |
| `SOM` | `SOM`             | Start-of-month    |
| `EOM` | `EOM`             | End-of-month      |

### Reading the parts

```python
from xxcommon.rdate import RDate, TENOR_FREQUENCY

rd = RDate('3M')
assert rd.count == 3                              # int (can be negative)
assert rd.freq is TENOR_FREQUENCY.MONTH
assert rd.symbol() == '3M'
assert str(rd) == '3M'                            # via Nucleus.to_str
```

### Applying to a date

```python
from datetime import date

from core_10x.exec_control import CACHE_ONLY
from xxcommon.rdate import RDate, BIZDAY_ROLL_RULE
from xxcommon.xxcalendar import Calendar

with CACHE_ONLY():
    cal = Calendar(_replace=True, name='US', non_working_days=[
        date(2025, 1, 1), date(2025, 7, 4), date(2025, 12, 25),
    ])
    out = RDate('1Y').apply(date(2025, 6, 16), cal, BIZDAY_ROLL_RULE.FOLLOWING)
    assert out == date(2026, 6, 16)
```

Available roll rules: `BIZDAY_ROLL_RULE.PRECEDING`, `FOLLOWING`, `MOD_PRECEDING`, `MOD_FOLLOWING`, `NO_ROLL`.

Chain several tenors at once:

```python
from datetime import date

from core_10x.exec_control import CACHE_ONLY
from xxcommon.rdate import RDate, BIZDAY_ROLL_RULE
from xxcommon.xxcalendar import Calendar

with CACHE_ONLY():
    cal = Calendar(_replace=True, name='US', non_working_days=[])
    out = RDate.apply_rule(date(2023, 1, 15), cal, BIZDAY_ROLL_RULE.NO_ROLL, '3M,1Y')
    assert out == date(2024, 4, 15)
```

### Arithmetic and unit conversion

```python
from xxcommon.rdate import RDate, TENOR_FREQUENCY

assert (RDate('6M') * 2).symbol()      == '12M'
assert (3 * RDate('6M')).symbol()      == '18M'
assert (RDate('6M') / 2).symbol()      == '3M'
assert RDate('6M') / RDate('3M')       == 2.0
assert (RDate('6M') + RDate('3M')).symbol() == '9M'

assert RDate('1Y').conversion_freq_multiplier(TENOR_FREQUENCY.MONTH) == 12
RDate('1Y').equate_freq(RDate('12M'))   # both expressed in their common frequency
```

Conversions across frequency families that don’t share a base (e.g. `YEAR` ↔ `BIZDAY`) raise `ValueError`.

### Schedules

```python
from datetime import date

from core_10x.exec_control import CACHE_ONLY
from xxcommon.rdate import RDate, BIZDAY_ROLL_RULE, PROPAGATE_DATES
from xxcommon.xxcalendar import Calendar

with CACHE_ONLY():
    cal = Calendar(_replace=True, name='US', non_working_days=[])

    starts, ends, all_dates = RDate('3M').period_dates(
        date(2023, 1, 15), date(2023, 7, 15),
        cal, BIZDAY_ROLL_RULE.NO_ROLL,
        PROPAGATE_DATES.FORWARD, allow_stub=True,
    )
    assert all_dates == [date(2023, 1, 15), date(2023, 4, 15), date(2023, 7, 15)]

    starts, ends, all_dates = RDate('3M').period_dates_for_tenor(
        date(2023, 1, 15), RDate('9M'),
        cal, BIZDAY_ROLL_RULE.NO_ROLL,
        PROPAGATE_DATES.BACKWARD,
    )
```

`PROPAGATE_DATES.BACKWARD` is the convention for most G10 interest-rate swaps.

---

## `Calendar` — business-day calendars

```python
from datetime import date

from core_10x.exec_control import CACHE_ONLY
from xxcommon.xxcalendar import Calendar

with CACHE_ONLY():
    us = Calendar(_replace=True, name='US', non_working_days=[
        date(2025, 1, 1), date(2025, 7, 4), date(2025, 12, 25),
    ])

    assert us.is_bizday(date(2025, 7, 4)) is False    # holiday
    assert us.next_bizday(date(2025, 7, 4)) == date(2025, 7, 5)
    assert us.prev_bizday(date(2025, 7, 4)) == date(2025, 7, 3)
    us.advance_bizdays(date(2025, 7, 3), 3)            # skips Jul 4
```

> Only listed dates are treated as non-working — weekends are *not* implied. Add Saturdays/Sundays to `non_working_days` if you want a typical 5-day week, or compose with another calendar that already encodes them.

Combine calendars with set algebra; the result is itself a `Calendar`:

```python
from datetime import date

from core_10x.exec_control import CACHE_ONLY
from xxcommon.xxcalendar import Calendar

with CACHE_ONLY():
    Calendar(_replace=True, name='US', non_working_days=[date(2025, 1, 1), date(2025, 7, 4)])
    Calendar(_replace=True, name='UK', non_working_days=[date(2025, 1, 1), date(2025, 12, 26)])

    union = Calendar.union('US', 'UK')          # OR  — non-working in either
    inter = Calendar.intersection('US', 'UK')   # AND — non-working in both

    assert date(2025, 7, 4) in union.non_working_days
    assert date(2025, 7, 4) not in inter.non_working_days
    assert date(2025, 1, 1) in inter.non_working_days
```

Per-instance overlays via `CalendarAdjustment`:

```python
from datetime import date

from core_10x.exec_control import CACHE_ONLY
from xxcommon.xxcalendar import Calendar, CalendarAdjustment

with CACHE_ONLY():
    Calendar(_replace=True, name='US', non_working_days=[date(2025, 1, 1)])
    CalendarAdjustment(_replace=True, name='SOFR', add_days=[date(2019, 4, 4)])

    sofr_us = Calendar(name='US', adjusted_for='SOFR')
    assert date(2019, 4, 4) in sofr_us.non_working_days
```

`Calendar` is a `Traitable`, so the usual rules apply. See [Core Concepts](../GETTING_STARTED.md#core-concepts) and [Setting Non-ID Traits at Construction: `_replace` and `_update`](../GETTING_STARTED.md#setting-non-id-traits-at-construction-_replace-and-_update) in `GETTING_STARTED.md` for how `_replace=True` / `_update=True` interact with shared-by-ID semantics.

---

## `Curve` and `DateCurve` — interpolated time series

`Curve` and `DateCurve` are `AnonymousTraitable`s, so they don’t need a storage context — each instance is independent. `value(t)` requires `beginning_of_time` to be set (it’s the lower bound below which `value()` returns `nan`).

```python
from xxcommon.curve import Curve, IP_KIND

c = Curve(times=[0.0, 1.0, 2.0, 3.0], values=[100.0, 110.0, 105.0, 102.0])
c.beginning_of_time = 0.0

c.value(0.5)                                # linear interp (default)

c.update(1.5, 108.0)                        # insert / overwrite a node
c.set_curve_params(ip_kind=IP_KIND.CUBIC)   # cubic needs >= 4 nodes
c.set_curve_params_to_flat_extrapolate()
```

```python
from datetime import date

from xxcommon.curve import DateCurve

dc = DateCurve()
dc.update(date(2025, 1, 1), 100.0)
dc.update(date(2025, 6, 1), 102.0)
dc.beginning_of_time = date(2025, 1, 1)

dc.value(date(2025, 3, 15))
dc.dates_values(min_date=date(2025, 2, 1))
```

Available `IP_KIND` values: `LINEAR`, `NEAREST`, `NEAREST_UP`, `PREVIOUS`, `NEXT`, `ZERO`, `SLINEAR`, `QUADRATIC`, `CUBIC`, `NO_INTERP`. Each carries a minimum-points label used by `min_curve_size`.

`DateCurve` stores times internally as integer day offsets from `1970-01-01`; expose dates via `dates`, `start_time()`, `end_time()`, `dates_values(...)`.

---

## `Event` and `EventProcessor` — timestamped event streams

`xxcommon.event.Event` and `xxcommon.event_processor.EventProcessor` provide a small framework for
timestamped, append-only event streams and watermark-based processing of them.

### `Event`

`Event` is an `EventBase` subclass (see [Traitable store-side traits](../GETTING_STARTED.md#traitable-store-side-traits)
in `GETTING_STARTED.md`) — every event carries store-side `_at` (`T.TS_TIME`) and `_who`
(`T.TS_USER`) traits stamped on save, so events are naturally ordered and attributable without
application code setting them.

| Method | Purpose |
|---|---|
| `Event.between(start, end, including_start=True, including_end=True)` | Events with `_at` in `[start, end]`; either `start` or `end` may be omitted for an open-ended range. |
| `Event.penultimate(when)` | The single event immediately before `when`, or `None`. |
| `Event.uuid7_from_dt(dt)` | Lowest possible UUID v7 for a given `datetime` — a sortable cursor/boundary ID that depends only on time. |

```python
from datetime import datetime, timedelta
from core_10x.traitable import T
from infra_10x.mongodb_store import MongoStore
from xxcommon.event import Event

class PriceTick(Event):
    ticker: str = T()
    price: float = T()

with MongoStore.instance(hostname='localhost', dbname='myapp'):
    PriceTick(ticker='AAPL', price=189.0).save()
    PriceTick(ticker='AAPL', price=190.5).save()

    recent = PriceTick.between(datetime.utcnow() - timedelta(minutes=5), None)
```

### `EventProcessor`

`EventProcessor` is a `Traitable` base class for consuming one or more `Event` subclasses through
class-name-dispatched handlers, tracking progress with a persisted per-class watermark so a
restart resumes cleanly instead of reprocessing or missing events.

Declare inputs (and, optionally, outputs) via subclass keyword args, and a
`<EventClassName>_process(self, event)` method for each input class:

```python
from core_10x.traitable import T
from infra_10x.mongodb_store import MongoStore
from xxcommon.event import Event
from xxcommon.event_processor import EventProcessor

class OrderPlaced(Event):
    order_id: str = T()

class OrderFilled(Event):
    order_id: str = T()

class OrderBook(EventProcessor, inputs=(OrderPlaced,), outputs=(OrderFilled,)):
    name: str = T(T.ID)

    def OrderPlaced_process(self, event: OrderPlaced) -> None:
        OrderFilled(order_id=event.order_id).save()

with MongoStore.instance(hostname='localhost', dbname='myapp'):
    book = OrderBook(name='main')
    n = book.process_pending_events()  # loads pending OrderPlaced events, dispatches, advances watermark, saves
```

Key points:

- **Class-name dispatch, validated at class-definition time**: `__init_subclass__` checks that
  every declared input class has a matching `<ClassName>_process(self, event)` method with the
  right signature, so a missing or mistyped handler fails immediately instead of silently
  dropping events.
- **One watermark per input class, one query per store**: `pending_events()` computes a watermark
  per store server (so multiple input classes sharing a store share one query), loads events
  strictly after each class's last-processed watermark, and returns them sorted by `_at`.
- **`process_pending_events()`** loads pending events, dispatches each to its handler (skipping
  any for which `needs_processing()` returns `False` — override to filter), advances and persists
  the watermark via `save()`, and returns the number of events processed.
- **`advance(watermarks)`** merges new watermarks into `last_watermarks` and saves directly — use
  it if you need custom control over when progress is committed.

---

## Tests

`xxcommon` tests do not use MongoDB. Run them with:

```bash
uv run pytest xxcommon/unit_tests/
```

Manual / exploratory snippets live in `xxcommon/manual_tests/`.

The Python code blocks above are exercised by `core_10x/unit_tests/test_documentation.py`, which extracts ```python fences from project docs (now including this file) and `exec()`s them.
