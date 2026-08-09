# AadcKernel — a reusable, generic AADC kernel for any traitable computation

`xxfin/jit_aadc/aadc_kernel.py` generalizes the pattern demonstrated in
`manual_tests/aadc_ccy_forward_test.py`: record an AADC kernel once for a given computed trait,
discover its market-data dependencies automatically, then reprice (and optionally get adjoints)
many times without re-recording. It isn't tied to `CcyForward.price` -- it works for any
`Traitable` trait whose computation is driven by `SingleMktQuote`-derived market data.

## Why this exists

Building an AADC kernel by hand (as in `aadc_ccy_forward_test.py`) means manually:
- collecting every market quotable feeding the computation,
- wrapping each quote as an `idouble` and marking it as a kernel input,
- recomputing the target trait under `AADCContext` recording,
- marking the result as a kernel output,
- and building the `inputs`/`request` dicts `evaluate_kernel` expects.

`AadcKernel` does all of this once, generically, for any `bound_trait` -- so new pricing
functions get AADC acceleration for free, without writing this boilerplate again.

## Core concepts

- **`BoundTrait`** (`obj.T.trait_name`) is the `(object, trait)` pair identifying what to record
  -- e.g. `cf.T.price`. See `GETTING_STARTED.md`'s `.T` accessor reference for the other forms.
- **`MktDeps`** (a `GraphDeps` subclass, see `xxfin/mkt_quotable.py`) walks the dependency graph
  built while evaluating the bound trait under `GRAPH_ON`, and yields every `SingleMktQuote`
  instance (by default; `target_class`/`target_trait_names` are overridable) that the computation
  actually depends on -- this is how market dependencies are discovered automatically rather than
  being hand-collected.
- **Market dependency keys**: every market input is identified by `(cls, quotable_id)` -- the
  quotable's class and its raw `ID` (from `GraphDeps.deps(objects=False)`, the "optimized" path
  that never constructs a Python instance for the leaf nodes). All of `input_handles`, `inputs`,
  and the `market_values`/`adjoints` parameters below are keyed this way.
- **Perturbation**: each discovered quote's cached graph value is replaced with an `idouble` via
  `GraphDeps.perturb()` (writes directly into the graph cache and invalidates the root trait so
  it recomputes) -- this is what makes the *second* evaluation of the bound trait AADC-active.

## API

```python
kernel = AadcKernel(bound_trait, graph=None)
kernel.build()
```
- `bound_trait`: e.g. `cf.T.price`.
- `graph`: an existing `BTraitableProcessor` (from `GRAPH_ON()`) to build on, or `None` to create
  a fresh one. Pass an existing graph if you want the kernel's recording to share cached state
  with other work already running under that graph.
- `build()`: evaluates the bound trait once (off recording, to prime the dependency graph),
  discovers its market dependencies via `MktDeps`, perturbs each with an `idouble` input, records
  the kernel by re-evaluating the bound trait under `AADCContext`, and marks the result as the
  kernel's output.

```python
value = kernel.eval(market_values=None)
```
Evaluates the recorded kernel -- no derivatives requested, so this is the cheap path.
`market_values` is an optional `{(cls, quotable_id): value}` override of the values recorded at
`build()` time; any key not present falls back to the recorded value. A value may be a scalar or
an array -- if any override is array-valued, the kernel evaluates one pass per array element (all
array-valued overrides must share the same length), and `value` comes back as an array too. This
is the natural way to reprice under many market scenarios in a single call.

```python
value, adjoints = kernel.eval_with_adjoints(market_values=None, adjoints=None)
```
Same as `eval()`, but also computes `d(value)/d(quote)`. `adjoints` (the parameter) lets you
request derivatives for only a subset of the discovered dependencies -- pass a list of
`(cls, quotable_id)` keys; defaults to every dependency if omitted. Returns `(value,
adjoints_by_key)`, where `adjoints_by_key` is `{(cls, quotable_id): derivative}` -- scalars, or
arrays in lockstep with a batched `market_values` override.

## Example

```python
from xxfin.ccy import Ccy
from xxfin.ccy_forward import CcyForward
from xxfin.jit_aadc.aadc_kernel import AadcKernel

cf = CcyForward(denominated=Ccy('GBP'), end_date=date(2035, 12, 12))

kernel = AadcKernel(cf.T.price)
kernel.build()

price = kernel.eval()
price, adjoints = kernel.eval_with_adjoints()

# reprice under a bumped quote, without rebuilding the kernel
some_key = next(iter(kernel.input_handles))
bumped = kernel.inputs[kernel.input_handles[some_key]] + 0.0001
bumped_price = kernel.eval(market_values={some_key: bumped})
```

See `manual_tests/aadc_kernel_test.py` for a full runnable version, cross-checked against
`manual_tests/aadc_raw_ccy_forward_test.py`'s hand-built reference values.

## Measuring "acceleration" honestly: on-graph vs off-graph baseline

When benchmarking `kernel.eval()` against a plain Python `traitable.some_trait` access, the
choice of baseline changes the result by roughly **three orders of magnitude**, and both numbers
are legitimate -- they just answer different questions:

- **Off-graph baseline** (no `GRAPH_ON` active): a `Traitable` gets no cross-call caching at all,
  so *every* access recomputes everything from scratch -- for `CcyForward.price` that's the full
  curve bootstrap, calendar work, etc., repeated on the 1st, 2nd, and 3rd call alike (measured:
  ~550ms-850ms per call, every call). Against that baseline, `kernel.eval()` (~350-520us) comes
  out to roughly **1000-1600x**.
- **On-graph baseline** (`GRAPH_ON` active, one fresh computation): a single genuine
  recomputation under graph mode, with all its caching benefits already applying, measured at
  ~28ms for `CcyForward.price`. Against that baseline, `kernel.eval()` comes out to roughly
  **55-75x**.

Which comparison is meaningful depends on whether the code path being replaced by
`AadcKernel` would actually run on-graph or off-graph in production. Don't quote a bare
"Nx acceleration" without saying which baseline it's against -- see
`manual_tests/aadc_kernel_test.py`, which measures the on-graph number by wrapping the Python
baseline in the same `GRAPH_ON` instance passed into `AadcKernel(..., graph=graph)`.

## A landmine in `AADCContext`: global builtin patching

`AADCContext.__enter__` patches `builtins.abs`/`min`/`max` (and several `math.*` functions)
*process-wide* for the duration of recording -- not scoped to just the computation being
recorded. `aadc.math.abs` unconditionally promotes its argument to an `idouble`, even for a
plain Python `int` (confirmed: `aadc.math.abs(0)` returns `idouble(0.00e+00)`, with or without an
active recording). This means *any* unrelated code that happens to call `abs()`/`min()`/`max()`
while a kernel is recording gets silently contaminated -- observed concretely as
`dateutil.relativedelta._fix()`'s internal `abs(self.seconds) > 59` check turning into an
`ibool` comparison and raising `ibool->bool conversion` deep inside date-rolling logic during
swap bootstrapping. This was intermittent across otherwise-identical runs with no code changes --
consistent with a known flakiness/state issue in the `aadc` library itself around repeated
recordings in one process, not a bug in `AadcKernel` or the bootstrap code. If it recurs, retrying
the run is a reasonable first step; if it's frequent, the patched-builtins window may need
narrowing (e.g. only patching within the specific call graph being recorded, if `aadc` exposes a
way to do that) rather than leaving it global for the whole process.

## Prerequisite: safe re-evaluation under `GRAPH_ON`

`build()` evaluates the bound trait *twice* under the same `GRAPH_ON` graph -- once to prime
dependencies, once (perturbed) to record. For computations that internally bootstrap a curve
(e.g. `ZeroRateCurve.payload_get`, which incrementally builds a `RateCurve` via a root-finder),
this re-entrant, on-graph evaluation used to trip the `write-during-read` guard in
`core_10x`/`cxx10x` (a getter mutating a graph node it depends on while still evaluating). That's
fixed via `UPWARD_DEPS_OFF()` in `xxcommon/py_curve.py` and `xxfin/root_solver.py` (backed by
`UpwardDepsOff` in `cxx10x/core_10x/btraitable_processor.h`). Without that fix, `AadcKernel` would
fail on any bound trait whose dependency chain includes curve bootstrapping.
