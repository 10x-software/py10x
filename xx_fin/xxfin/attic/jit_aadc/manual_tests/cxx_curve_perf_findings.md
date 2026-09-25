# Why AADC gives ~78x but the C++ curve/bootstrap path only gives ~7x

## The observation

`aadc_ccy_forward_test.py` reports `AADC acceleration = 77.6` (AADC-recorded kernel vs plain
Python baseline). Separately, switching `xxfin` to its C++ curve/zrc-bootstrap implementation
(`XXFIN_USE_CXXFIN=True` + `XXCOMMON_USE_CXX_CURVE=True`) only yields roughly 7x over the pure
Python implementation. Given both are "the fast path," the size of the gap is worth explaining
rather than assuming.

## Profiling result

Profiled a warm (post-warmup, cache already populated) `cf.price` call under the C++ curve/
bootstrap path -- see the snippet below. Total: **0.111s**, 9289 function calls. Self-time
("tottime") breakdown, top entries:

| function | self time | calls |
|---|---|---|
| `xxcalendar.py:_non_working_days_get` | 0.053s | 429 |
| `core_10x/trait.py:__get__` (trait descriptor dispatch) | 0.048s | 845 |
| `xxcalendar.py:is_bizday` | 0.007s | 267 |
| `cxxfin.discount_factor` (the actual C++ curve math) | 0.000s | 40 |

The top two rows alone are ~91% of total time. The compiled C++ discount-factor computation --
the thing that was actually ported to C++ -- is essentially free (rounds to 0.000s across 40
calls). It was never the bottleneck.

## What this means

The ~7x number isn't "C++ arithmetic vs Python arithmetic." It's business-day/calendar
calculations (recomputed repeatedly -- 429 calls for a single price) and Python's trait-descriptor
dispatch (845 `__get__` calls) that dominate. Porting the curve storage/bootstrap to C++ does
nothing about either of those, because neither one is curve-related.

AADC's much larger speedup comes from a different mechanism entirely: once `record_kernel()`
captures the computation, evaluation replays as a flat numeric tape with **zero** calendar logic
and **zero** trait-graph traversal -- it eliminates the actual bottleneck (calendar + trait
dispatch), not the part that was already free (curve math). That's why a JIT-recorded kernel can
outrun a genuinely compiled backend that's still driven step-by-step from Python: it isn't
competing on arithmetic speed, it's competing on how much per-call Python/object-system overhead
survives into the hot path.

## Profiling snippet used

Run with:
```
XX_MAIN_TS_STORE_URI=mongodb://localhost/xx_fin
XXCOMMON_USE_CXX_CURVE=True
XXFIN_DEFAULT_PRICING_CONTEXT_NAME=Abu Dhabi 20251010
XXFIN_USE_CXXFIN=True
```

```python
import cProfile
import pstats

from datetime import date
from xxfin.ccy import Ccy
from xxfin.ccy_forward import CcyForward

end_date = date(2035, 12, 12)
ccy      = Ccy.existing_instance(name='GBP')
cf       = CcyForward(denominated=ccy, end_date=end_date)

warmup_price = cf.price   # cold: mongo loads, calendar caches, etc -- discard

zrc = cf.disc_curve
for cls, qdict in zrc.quotables_by_class.items():
    for d, q in qdict.items():
        q.quote = float(q.quote)   # force ZeroRateCurve.payload to invalidate + re-bootstrap

pr = cProfile.Profile()
pr.enable()
price = cf.price
pr.disable()

print(f'price = {price}')

st = pstats.Stats(pr)
st.sort_stats('cumulative')
st.print_stats(35)

print('\n\n--- by total (self) time ---')
st.sort_stats('tottime')
st.print_stats(25)
```
