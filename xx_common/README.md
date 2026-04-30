# `xx_common`

Shared, finance-oriented building blocks layered on top of `core_10x`:

- **`xxcalendar`** — `Calendar` with non-working days, set algebra (union / intersection), and adjustments.
- **`rdate`** — `RDate` tenors (e.g. `'3M'`, `'1Y'`) with business-day roll rules and date schedules.
- **`curve`** — `Curve` / `DateCurve` with pluggable interpolation (`scipy.interpolate`).

For the broader project (concepts, install, tests, style), see [`README.md`](../README.md), [`INSTALLATION.md`](../INSTALLATION.md), and [`GETTING_STARTED.md`](../GETTING_STARTED.md) at the repository root.

---

## `RDate` — relative dates / tenors

An `RDate` is a `(count, freq)` pair describing an offset like *3 months* or *5 business days*. It can be constructed from a symbol string or from explicit parts.

### Construction

```python
from xx_common.rdate import RDate, TENOR_FREQUENCY

RDate('3M')                                       # 3 months
RDate('1Y')                                       # 1 year
RDate('-2Q')                                      # -2 quarters
RDate(freq=TENOR_FREQUENCY.MONTH, count=3)        # same as RDate('3M')
RDate(freq=TENOR_FREQUENCY.YEAR)                  # count defaults to 1
```

Supported frequency characters (see `FREQUENCY_TABLE` in `xx_common/rdate.py`):

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
rd = RDate('3M')
rd.count      # 3                        (int; can be negative)
rd.freq       # TENOR_FREQUENCY.MONTH
rd.symbol()   # '3M'
str(rd)       # '3M'   (via Nucleus.to_str)
```

### Applying to a date

```python
from datetime import date
from xx_common.rdate import RDate, BIZDAY_ROLL_RULE
from xx_common.xxcalendar import Calendar

cal = Calendar.existing_instance_by_id('US')
RDate('1Y').apply(date(2025, 1, 1), cal, BIZDAY_ROLL_RULE.FOLLOWING)
# -> date(2026, 1, 1) (rolled to the next business day if needed)
```

Available roll rules: `BIZDAY_ROLL_RULE.PRECEDING`, `FOLLOWING`, `MOD_PRECEDING`, `MOD_FOLLOWING`, `NO_ROLL`.

Chain several tenors at once:

```python
RDate.apply_rule(date(2023, 1, 15), cal, BIZDAY_ROLL_RULE.NO_ROLL, '3M,1Y')
# -> date(2024, 4, 15)
```

### Arithmetic and unit conversion

```python
RDate('6M') * 2          # RDate('12M')
3 * RDate('6M')          # RDate('18M')
RDate('6M') / 2          # RDate('3M')
RDate('6M') / RDate('3M')# 2.0
RDate('6M') + RDate('3M')# RDate('9M')

RDate('1Y').conversion_freq_multiplier(TENOR_FREQUENCY.MONTH)   # 12
RDate('1Y').equate_freq(RDate('12M'))                            # both expressed as months
```

Conversions across frequency families that don’t share a base (e.g. `YEAR` ↔ `BIZDAY`) raise `ValueError`.

### Schedules

```python
rd = RDate('3M')
starts, ends, all_dates = rd.period_dates(
    date(2023, 1, 15), date(2023, 7, 15),
    cal, BIZDAY_ROLL_RULE.NO_ROLL,
    PROPAGATE_DATES.FORWARD, allow_stub=True,
)
# all_dates: [Jan 15, Apr 15, Jul 15]

starts, ends, all_dates = RDate('3M').period_dates_for_tenor(
    date(2023, 1, 15), RDate('9M'),
    cal, BIZDAY_ROLL_RULE.MOD_FOLLOWING,
    PROPAGATE_DATES.BACKWARD,
)
```

`PROPAGATE_DATES.BACKWARD` is the convention for most G10 interest-rate swaps.

---

## `Calendar` — business-day calendars

```python
from datetime import date
from xx_common.xxcalendar import Calendar, CalendarAdjustment

us = Calendar(_replace=True, name='US', non_working_days=[
    date(2025, 1, 1), date(2025, 7, 4), date(2025, 12, 25),
])

us.is_bizday(date(2025, 7, 4))   # False
us.next_bizday(date(2025, 7, 4)) # date(2025, 7, 7)
us.advance_bizdays(date(2025, 7, 3), 3)
```

Combine calendars with set algebra; the result is itself a `Calendar`:

```python
union = Calendar.union('US', 'UK')          # OR  — non-working in either
inter = Calendar.intersection('US', 'UK')   # AND — non-working in both
```

Per-instance overlays via `CalendarAdjustment`:

```python
CalendarAdjustment(_replace=True, name='SOFR', add_days=[date(2019, 4, 4)])
sofr_us = Calendar(name='US', adjusted_for='SOFR')
```

`Calendar` is a `Traitable`, so the usual rules apply. See [Core Concepts](../GETTING_STARTED.md#core-concepts) and [Setting Non-ID Traits at Construction: `_replace` and `_update`](../GETTING_STARTED.md#setting-non-id-traits-at-construction-_replace-and-_update) in `GETTING_STARTED.md` for how `_replace=True` / `_update=True` interact with shared-by-ID semantics.

---

## `Curve` and `DateCurve` — interpolated time series

```python
from datetime import date
from xx_common.curve import Curve, DateCurve, IP_KIND

c = Curve(times=[0.0, 1.0, 2.0], values=[100.0, 110.0, 105.0])
c.set_curve_params(ip_kind=IP_KIND.CUBIC)
c.value(1.5)
c.update(1.5, 108.0)             # insert / overwrite a node
c.set_curve_params_to_flat_extrapolate()

dc = DateCurve(beginning_of_time=date(2025, 1, 1))
dc.update(date(2025, 1, 1), 100.0)
dc.update(date(2025, 6, 1), 102.0)
dc.value(date(2025, 3, 15))
dc.dates_values(min_date=date(2025, 2, 1))
```

Available `IP_KIND` values: `LINEAR`, `NEAREST`, `NEAREST_UP`, `PREVIOUS`, `NEXT`, `ZERO`, `SLINEAR`, `QUADRATIC`, `CUBIC`, `NO_INTERP`. Each carries a minimum-points label used by `min_curve_size`.

`DateCurve` stores times internally as integer day offsets from `1970-01-01`; expose dates via `dates`, `start_time()`, `end_time()`, `dates_values(...)`.

---

## Tests

`xx_common` tests do **not** require MongoDB. Run them with:

```bash
uv run pytest xx_common/unit_tests/
```

Manual / exploratory snippets live in `xx_common/manual_tests/`.
