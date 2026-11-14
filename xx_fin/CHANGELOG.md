# Changelog

All notable changes to `py10x-fin-base` and `py10x-fin-base-cxx` are documented in this file. The two packages are co-released at the same version. `py10x-core` and its C++ packages have their own [changelog](../CHANGELOG.md).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Changes since **0.1.2**. The next release is 0.2.0.

### Added
- **`FinBasket` and instrument lifecycle** (`xxfin/fin_instrument.py`, `xxfin/ccy_forward.py`): `FinBasket`, a core `Basket` of `FinInstrument`s aggregated by `FIN_AGGREGATOR.PRICE` / `PRICE_CCY`, replaces `PreBasket` as `FinInstrument.leaves`. Lifecycle API: `next_lifecycle_date(after)`, `lifecycle_transform()` (what one unit becomes as of the pricing context's `md_date`, or `XNone`) and `FinBasket.fire_lifecycle()`. A `CcyForward` becomes a `CcyUnit` on its `end_date`.
- **`IRSwapQuotable` leg schedules**: `fixed_start_dates` / `fixed_end_dates` / `fixed_pay_dates` / `fixed_dc_fractions`, `pay_date` (the last payment) and `swap_rate_calc(rate_curve, today)`. The py and C++ bootstraps read their schedules from the quotable.
- **`RateCurve` schedule helpers** (`xxfin/py_rate_curve.py`): `period_dates`, `discount_factors_by_date`, `annuity_for_dc_fractions`, `swap_float_leg_for_period_dates`, `swap_float_leg_simple_compounding`, `swap_rate_for_period_dates`; a date shared by both legs is discounted once.
- **`SNAPSHOT.MANUAL`**: snapshot type for manual market-data overrides, e.g. of a fixing.

### Changed
- **Static market dependencies retired** (breaking): `FinInstrument.mkt_deps`, `mkt_deps_for_discounting` and `mkt_deps_for_ccy` are gone; discover dependencies at run time with `MktDeps`.
- **Swap bootstrap** (numerical): both legs roll backward from maturity with a front stub (was forward, no stub), and the floating leg is valued period by period at the market's `tenor_frequency`. The root search tries ±2% around the quote first (was `quote / 2 .. 2 * quote`). Bootstrapped curve points move accordingly.
- **`RateCurve.swap_rate_simple_compounding`** (breaking): new `swap_freq` argument after `fixed_dc_convention`.
- **`cxxfin.bootstrap_swap`** (breaking, py10x-fin-base-cxx): takes per-date node vectors and the fixed / floating leg terms in place of `t_today_last` / `last_dc_frac` / `df_spot` / `gap_*`, with no defaults. `solve_swap(zrc, quotable, mc, today)` (py and cxx) takes the quotable in place of `spot_date, swap_tenor, quote`.
- **pybind11 3.1.0** (from 2.13.6; py10x-fin-base-cxx) (breaking, binary): `cxxfin` must be built against a py10x-kernel on the same pybind11 version.

### Fixed
- **Swap floating leg with a payment delay** (py and C++ bootstraps): with a nonzero `settle_offset` the leg was valued as the no-delay `df(spot) - df(last_pay)`; each coupon is now discounted from its own pay date.
- **Cash deposits**: `IRCashDepositQuotable.pay_date` is the end date (it was shifted by the settle offset), so deposit curve points sit at maturity.
- **C++ bootstrap**: no longer fails on a curve with no points yet, and anchors the beginning of time the same way as the py bootstrap.
- **`ZeroRateCurveQL`**: deposit and OIS pillar dates now match the native bootstrap (deposit fixing days counted on the calendar that set the start date; OIS schedules generated backward without end-of-month); QuantLib's process-global evaluation date is restored afterwards.
- **Dev market data**: the 10Y USD/JPY forward quote was 100× too small.

## [0.1.2] - 2026-10-02

Changes since **0.1.1**. Pinned to py10x-core 0.3.2.

### Added
- **`ZeroRateCurveQL`** (`xxfin/ir_zero_rate_curve_ql.py`, `xxfin/ql_adapter.py`): QuantLib `PiecewiseLinearZero` bootstrap of deposits and OIS swaps, an alternative to the native bootstrap; `QL` maps xxfin day counts, roll rules, tenors, compounding and currencies to QuantLib. `ZeroRateCurve` is a `SelectableTraitableClass`, and `FinInstrument`, `FXForwardCurve` and `FXFundedDiscRateCurve` build `ZeroRateCurve.selected_class()`.
- **`aadc` extra**: `py10x-fin-base[aadc]` forwards to `py10x-core[aadc]`.

### Changed
- **`MktConventions` is a `NamedTraitable`** keyed by `mkt_name`: `IRRateMktConventions(name)` replaces `existing_instance(mkt_name=name)`, and an unknown name raises.
- **`MktDeps(graph, bound_trait, inputs_spec=None)`** (breaking): follows the new `GraphDeps` constructor; the default spec is `{MktQuotable: leaf traits}`.
- **`CcyCross`**: a cross with neither side deliverable is allowed (`is_deliverable` false, `delivery_ccy` `None`) instead of failing an assertion. `is_same_ccy_cross` / `is_dollar_cross` accept `Ccy` objects or names; `is_same_ccy_cross` asserts on a malformed cross instead of returning `False`. `Ccy.verified(name)` no longer queries the store.
- **AADC**: `aadc` is no longer a required dependency (use the `aadc` extra). `xxfin.jit_aadc` is archived under `xxfin/attic/`, superseded by `xxcommon.jit_aadc`.
- **`FXForwardQuotable.dc_fraction`** removed.

### Fixed
- **`IRSwapQuotable` schedules**: periods stepped by the swap tenor instead of the market's `tenor_frequency`, and the `incremental_dc_fractions` getter was misnamed, so it never ran.
- **O/N deposits**: `IRCashDepositQuotable.start_date` for `1B` is the market-data date, not spot.
- **`CcyCross.is_normal_cross`** passed `Ccy` objects where currency names were expected, so it did not recognize normal crosses.

## [0.1.1] - 2026-08-13

No code changes; pinned to py10x-core 0.3.1 and added PyPI classifiers.

## [0.1.0] - 2026-08-13

Initial release, pinned to py10x-core 0.3.0. Install `py10x-fin-base` only (imports `xxfin` / `cxxfin`; `py10x-fin-base-cxx` is transitive). Requires Python `>=3.11,<3.14`. See [`README.md`](README.md).
