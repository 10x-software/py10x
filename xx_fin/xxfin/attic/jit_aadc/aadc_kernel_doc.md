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
  ~750-760ms per call, every call, on `aadc` 2.8.0). Against that baseline, `kernel.eval()`
  (~65-80us) comes out to roughly **9300-11100x**.
- **On-graph baseline** (`GRAPH_ON` active, one fresh computation): a single genuine
  recomputation under graph mode, with all its caching benefits already applying, measured at
  ~24ms for `CcyForward.price` on `aadc` 2.8.0. Against that baseline, `kernel.eval()` comes out to
  roughly **300-370x**.

Which comparison is meaningful depends on whether the code path being replaced by
`AadcKernel` would actually run on-graph or off-graph in production. Don't quote a bare
"Nx acceleration" without saying which baseline it's against **and which `aadc` version produced
it** -- these figures are hardware- and version-dependent, so a number without both is not
reproducible. See `manual_tests/aadc_kernel_test.py`, which measures the on-graph number by
wrapping the Python baseline in the same `GRAPH_ON` instance passed into
`AadcKernel(..., graph=graph)`.

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

## Known limitation (unresolved): value-dependent branches can hide market dependencies

`MktDeps`/`GraphDeps` discovers market dependencies from **one** priming evaluation of the bound
trait, done *before* `AADCContext` is entered. If a getter branches on a value that is itself a
market dependency (`if obj.some_trait < threshold: blah() else: blah2()`), only the taken
branch's quotables get discovered, `perturb()`-ed to `idouble`, and `mark_as_input()`-ed. Since
`AadcKernel` is meant to be **recorded once and replayed across many market scenarios**
(`kernel.eval(market_values=...)`), a later scenario that would flip the branch gets a silently
wrong answer: the untaken branch's quotables are frozen constants in the tape, not real inputs
(`_lookup_handle` raises `Unknown market dependency` if you try to override one). Live risk only
when the branch condition depends on something that can actually vary across replay scenarios; a
branch on a static/structural value is safe. This is the general limitation any "record once,
replay for many inputs" system hits when control flow is input-dependent (tracing JITs, other AAD
libraries) -- not a bug specific to `MktDeps`.

**`aadc.iif`/`ibool` do not solve this.** `iif(cond, a, b)` selects between values *already
computed* in the current pass -- it can't discover a quotable the priming pass never executed.
It only helps *after* discovery is already solved for both branches.

**`aadc.branching` (`@branching_function` / `BranchScope` / `smart_assign`) is closer, but not
sufficient by itself.** During actual recording (`is_recording()` true), `bm.if_`/`elif_`/`else_`
return `True` for every branch, so all branches genuinely execute and `smart_assign` correctly
masks the result via the branch's `ibool` -- this is the library's real, proper answer to
"encode a branch decision in one reusable tape." But during eager/priming evaluation
(`is_recording()` false), `bm.if_()` returns the real bool -- ordinary short-circuiting, one
branch only. So `branching` fixes *recording*, not *discovery* -- the same split as `iif`, one
level up.

### Open directions (none implemented, not yet decided which to pursue)

1. **Redesign discovery to run under recording semantics.** If priming itself happened inside
   `record_kernel()` (with the full candidate universe of quotables pre-perturbed rather than
   discovered by executing once), `BranchScope`-written getters would have every branch
   discovered and correctly masked in a single pass -- no runtime guard needed. Bigger lift:
   requires perturbing a declared candidate set up front (not discovering it), and rewriting
   conditional getters to use `BranchScope` instead of plain `if`.
2. **Guard-based staleness detection, backed by a growing family of kernels keyed by branch
   signature** -- the current leading design, decided in shape though not yet implemented. The
   branch *condition* is always evaluated regardless of outcome, so its inputs are already
   correctly discovered -- only the branch bodies have the gap. Mark each condition as an extra
   kernel output at record time (cheap, inputs already wired); this doubles as a **branch
   signature** for the kernel. A wrapper maintains `kernels: dict[branch_signature, AadcKernel]`
   -- one ordinary, unmodified `AadcKernel` per distinct combination of branch outcomes actually
   encountered so far (no `BranchScope`/masked-recording redesign needed; each cached kernel is a
   plain single-branch recording exactly as today):
   - **Signature matches a cached kernel** -> dispatch straight to it. Fast path, no rebuild, no
     discovery -- this is the common case once a branch has been seen once.
   - **Signature is new** -> run the real top-level getter on-graph to discover this branch's
     dependencies (this is where a plain on-graph fallback answer would come from, if needed
     immediately), build a fresh `AadcKernel` for it, and **add** it to `kernels` under the new
     signature. Nothing already cached is touched or evicted -- this is what "extend without
     forgetting" means concretely: growing the family, never mutating or discarding an entry.
     (Not an option regardless -- confirmed via `_aadc_core.pyi`/introspection: `Functions` has
     only a no-arg constructor, no `.copy()`/`__copy__`/`__deepcopy__`, and no way to resume a
     stopped recording -- copy-then-extend isn't available at any level.)
   - **If even that discovery-and-build step fails or isn't safe to do inline** -> crash loudly
     (refuse to return a possibly-wrong number) or fall back to a plain on-graph answer for just
     that call (correct, no derivatives, nothing cached) -- the two remaining options, now scoped
     as fallbacks for *this* step rather than peers of the main dispatch logic.
   Still requires a conditional getter to explicitly expose its guard condition (cheaper ask than
   exposing the untaken branch's full computation), and needs to compose transitively across the
   whole dependency chain, not just the top-level getter.

### `dep_branch` -- the guard-registration primitive (decided shape, not yet built)

Belongs in `core_10x` (next to `GRAPH_ON`/`UPWARD_DEPS_OFF`), not in `xxfin.jit_aadc` -- this is a
dependency-law construct (registering a branch as part of the dependency graph), and AADC is just
its first consumer.

```python
if dep_branch(f"{__file__}:{lineno}", self.some_trait < threshold):
    return blah()
else:
    return blah2()
```

`dep_branch(guard_id, condition) -> condition` -- transparent passthrough, zero eager-mode
behavior change. Side effect: if a signature accumulator is active (only during an
`AadcKernel`-driven pass), appends `(guard_id, bool(condition))` to it; a `frozenset` of these
pairs is the branch signature (see prior section). `guard_id` = **file + line number of the call
site**, not a hand-picked label -- uniqueness must be structural, not a discipline requirement
(two `if` statements can't share a file+line); the condition's own source text can still serve as
a purely cosmetic label for logging.

**Open problem this doesn't solve on its own: a getter author can simply forget to use it**,
silently reproducing the original discovery gap while looking covered -- needs auto-instrumentation
via AST rewriting at class-definition time (precedent: pytest's assertion-rewriting), hooked
through `Traitable.__init_subclass__` opt-in, same pattern as `s_cxx_mixins` wiring.

**Adopted starting design: wrap every `If`, unfiltered ("trivialist," decided 2026-09-05).**
Rather than trying to precisely classify which `if`s are market-dependent (matching `cls.s_dir`,
plus a same-function forward taint-propagation pass to catch indirect cases like `x = self.trait;
y = x+1; if y < threshold: ...` -- a real dataflow analysis, itself a source of bugs, deferred as
a possible future optimization only), wrap *every* `If.test` in the getter unconditionally. This
trades a possible performance cost for eliminating an entire category of correctness risk (bugs in
a classifier that could itself under-cover), and the traded-away cost turns out to be smaller than
it first looks: a guard only fragments the kernel cache if its outcome actually *differs* across
replay scenarios. A structural check like `if x is None:` unrelated to market data comes out the
same every time market_values vary -- it becomes a constant entry in every signature, never
causing a mismatch. The only guards that ever cause fragmentation are the ones whose outcome
genuinely depends on something that varies -- exactly the ones that matter. Remaining cost of the
irrelevant ones: negligible bookkeeping (one extra call + one unchanging tuple per signature), not
cache effectiveness. Precise `s_dir`/taint-tracking classification is now a possible *later*
optimization, worth building only if real measurement shows fragmentation is an actual problem --
not built up front on faith.

No option preserves single-execution automatic discovery *and* guarantees completeness -- that
combination is impossible in general when control flow is genuinely value-dependent.

### How a guard actually becomes a kernel output

"Becoming an additional output" mechanically means one thing: `.mark_as_output()` gets called on
it -- the exact same call already used for the price (`res_active.mark_as_output()`). `condition`
in `dep_branch(guard_id, condition)` is just whatever the comparison expression evaluated to at
that call site -- a plain `bool` during the eager priming read (nothing to mark, plain `bool` has
no such method), an `ibool` during the actual recording read *if* the compared value was itself
perturbed to `idouble` (this is the moment marking is meaningful).

`dep_branch` itself stays AADC-agnostic -- it only appends `(guard_id, condition)` to whatever
accumulator is currently active via a `contextvars.ContextVar` (same pattern as `aadc.branching`'s
own `_active_func_bm`), or does nothing if none is active:

```python
_active_accumulator: contextvars.ContextVar[list | None] = contextvars.ContextVar(..., default=None)

def dep_branch(guard_id: str, condition):
    acc = _active_accumulator.get()
    if acc is not None:
        acc.append((guard_id, condition))
    return condition
```

`AadcKernel` (AADC-specific, not `dep_branch`) is what installs the accumulator around its
recording read, then drains it and calls `.mark_as_output()` on any entry that turns out to be a
real `ibool`, remembering the handle keyed by `guard_id`. Multiple named outputs (price + each
guard) go into one `deps` dict and one `evaluate_kernel(...)` call at replay time -- checking
every guard costs nothing extra, it's the same replay call, guard entries just carry no
input-handle list (no derivatives wanted for a boolean).

### Getting instrumented getters in place without a discovery pass

First draft of this needed 3 passes in `build()`: (1) uninstrumented priming, (2) walk that graph
to discover which (class, getter) pairs are even reachable for this bound trait, (3) instrument
just those and re-run. **Rejected -- too much machinery, and the reentrancy/staleness risk of
temporarily monkey-patching specific methods in place.**

**Adopted instead (2026-09-06): every *opted-in* trait gets its instrumented variant built once,
up front -- not discovered per bound-trait** (opt-in scope refined below, not every trait on every
class). Parallel to the existing `s_cxx_mixins` mechanism (a trait can already have more than one
getter implementation -- a C++ mixin can stand in for the Python one), but selected *dynamically
per call* rather than fixed once at class-definition time:

**Simplified and settled (2026-09-06): only one alt-getter-code type exists per process, ever.**
Not a dict of optimizer names -- a single slot:

- `XX_ALT_GETTER_CODE_TYPE` = a full dotted class path (e.g.
  `xxfin.jit_aadc.aadc_kernel.AadcKernel`), read **once, process-wide**, at first
  `Traitable.__init_subclass__`. That named class is asked to instrument each trait's Python
  getter (the trivialist AST rewrite) at class-definition time; the result is stored as a single
  `f_alt_get` slot per trait ("if any" -- some traits won't get one: no `if` to instrument, or a
  C++-mixin-provided getter with no Python source at all).
- **Dispatch is in `wrapper_f_get()` itself** -- real, existing C++ (`btrait_processor.cpp`,
  already read: `trait->wrapper_f_get(obj)`, called from both `get_value_on_graph` and
  `get_value_off_graph`). It checks a state var to choose `f_get` vs `f_alt_get`.
- **The state var is a single true global C++-side `bool`** (not `thread_local`, not a Python
  `contextvar`) -- a plain flag, cheap to check on the hot dispatch path, exposed to Python via a
  small pybind11 setter. `AadcKernel` sets it before its priming+recording reads, resets it in a
  `finally` after. **Explicit, accepted limitation**: this gives zero cross-thread safety, not
  just no same-thread reentrancy -- if any other thread ran `build()`, or even just normal pricing
  on some trait, while the flag was set, it would incorrectly pick up `f_alt_get` too. Chosen
  deliberately for simplicity, not an oversight.
- This still makes reachability stop mattering: whatever getters actually get touched during
  `build()`'s existing two passes (priming, recording) automatically run `f_alt_get` while the
  flag is set -- no separate discovery pass needed, `build()` stays two-pass.

### Scope: not just getters -- plain functions branch on trait values too

The `FinInstrument`-vs-`SyntheticMktData` class-scoping question above turned out to be too
narrow a framing. A getter commonly calls a **plain Python function** (a module-level helper, a
non-Traitable utility class method) that itself conditionally touches different traits, or
branches on a comparison whose outcome could vary across replay scenarios:

```python
def helper(obj, flag):
    if obj.some_trait < threshold:
        return obj.trait_a
    else:
        return obj.trait_b
```

Plain functions have **no equivalent of `wrapper_f_get()`** -- no single existing choke point
every call funnels through, so the whole class-hierarchy-based opt-in mechanism above (however
it's scoped) cannot reach them at all.

**A decorator-based opt-in for plain functions was proposed and rejected** -- same objection
already raised against relying on developer discipline for `dep_branch` itself: forgetting it is
silent, and its mere existence creates false confidence that coverage is handled. Inconsistent
with the whole reason discipline-based opt-in was rejected for getters in the first place.

**Settled shape (2026-09-07, not fully finalized -- see caveat below): two tiers, matching risk to
how rare the opt-in decision actually is.**

1. **Tier 1 -- automatic, zero opt-in risk.** *Any* getter, method, or classmethod defined
   directly on a Traitable subclass gets instrumented, full stop, no marker needed -- manageable
   from `__init_subclass__` exactly like `s_cxx_mixins` wiring already is: `cls.__dict__` (a
   class's own namespace, not inherited members) gives every callable it defines, not just
   recognized `*_get` trait getters, so ordinary helper methods a getter calls into are covered by
   the same mechanism, no separate handling needed. Implementation detail to remember when this
   gets built: `classmethod`/`staticmethod` are descriptors wrapping an underlying function
   (`.__func__`) -- instrumenting means unwrap, rewrite the inner function, re-wrap in the same
   descriptor type.
2. **Tier 2 -- explicit, but at module granularity, not function granularity.** Standalone
   helper functions/classes in genuine "library" modules (`root_solver.py`, `py_curve.py`) that
   don't themselves define any Traitable subclass are instrumented only if the *module* is
   explicitly marked -- one flag at the top of the file, not a decorator on every function inside
   it.

**Honest residual risk, consciously accepted, not resolved away:** tier 2 is still technically
opt-in, so the "forgetting is silent" objection isn't *eliminated* there, only moved to a much
coarser, much rarer decision -- creating a brand-new shared library module that several
`FinInstrument` getters call into is a rare, deliberate, architecturally-visible event, nowhere
near as easy to overlook as a decorator on one more function among hundreds written day to day,
but it is not an airtight structural guarantee the way tier 1 is. **Explicit judgment call: a
100% structural guarantee isn't achievable here without either instrumenting the entire codebase
indiscriminately or imposing real constraints on how ordinary Python gets written elsewhere, and
neither is worth it to close an already-narrow residual risk.** Consistent with the same tradeoff
already made for the trivialist `dep_branch` approach itself.

### Where the alternative code lives for a method, classmethod, or plain function (proposed, not finalized)

`wrapper_f_get()` gives trait getters a *free* choke point -- every getter call already goes
through it, so checking a flag there costs nothing beyond what was already happening. Regular
methods, classmethods, and plain functions in a marked module have **no such choke point at all**
-- ordinary Python name resolution, nothing intercepts it. That means the getters' "keep both
versions permanently present, check a flag at the one mandatory dispatch point" trick can't give
zero overhead here without *inventing* a new dispatch point -- and a permanent wrapper around
every such call would tax it forever, even when `AadcKernel` is never used.

**Proposed: monkey-patch specifically for these two cases -- the same technique rejected for
getters, but for a principled reason this time, not by default.** Getters got a non-monkey-patch
design *because* a free alternative existed; it doesn't exist here, so the tradeoff is different:

- **Storage**: build both versions at instrumentation time (class-definition time for
  methods/classmethods via `__init_subclass__`, import time for plain functions in a marked
  module) and store the alt version in a **registry**, not yet bound over the original name -- a
  single class-level dict (`cls.s_alt_methods: dict[str, callable]`, same shape as `s_cxx_mixins`
  being one named collection attribute) for methods/classmethods, and an analogous module-level
  dict for plain functions in a marked module.
- **Activation**: `AadcKernel`, at the exact moment it sets the C++-side global bool for getter
  dispatch, *also* walks these registries and temporarily rebinds each original class/module
  attribute to its alt version -- restoring the originals in the same `finally` that resets the
  C++ flag. True zero overhead when inactive (the original, unwrapped function is what's bound,
  identical to today), at the cost of the *same* single-global/no-thread-safety limitation already
  accepted for the C++ flag -- not a new risk, the same one showing up in a second place, kept in
  sync with it.

So: two different mechanisms by design -- flag-check-inside-an-existing-choke-point for getters,
monkey-patch-at-activation-time for everything else -- driven by which case actually has a free
dispatch point to piggyback on, not an inconsistency.

### A verification mode for the tier-2 residual risk (proposed, 2026-09-09)

Tier 2's residual risk (a library module someone forgot to mark) was accepted as a rare, coarse,
consciously-accepted gap rather than solved structurally. Idea to make that gap *detectable*
instead of pure faith: on a getter invocation, walk the current Python call stack and check that
every frame in it belongs to either a Traitable-subclass module (tier 1, auto-covered) or a
module explicitly marked for tier 2 -- flag anything else as a candidate coverage gap.

Refinements from discussion, before building this:

- **Check against the actually-instrumented set, not just "is the module marked."** A marked
  module can still have functions that were skipped (e.g. merely-imported names, filtered by
  `member.__module__ == module.__name__`). `EdgeDepsTracker.s_instrumented_classes` /
  `s_instrumented_modules` already record exactly which (class, method) / (module, function)
  pairs were instrumented -- compare each frame's code object against that known set (plus
  genuine trait getters via `s_dir`), which is more precise than re-deriving a coarser
  module-level signal.
- **Must be a separate, explicit diagnostic mode -- never on the hot path.** Stack-walking on
  every getter call (`inspect.stack()`, or even the cheaper `sys._getframe()` chain-walk) is real
  overhead unacceptable during normal operation or even normal AADC recording. Needs its own env
  var, true only during a deliberate audit run (a CI job, a one-off developer check).
- **Scope where the walk stops, or it drowns in stdlib/third-party noise.** Only inspect frames
  under the real package scope (`py10x`/`xx-fin-domain`); stop once outside it -- otherwise every
  audit run surfaces pytest/stdlib/numpy internals that were never expected to be instrumented.
- **Deduplicate.** The same unmarked helper shows up in the stack of every call that reaches it --
  collect a *set* of `(module, qualname)` pairs seen-but-not-instrumented, reported once at the
  end of a run, not a live warning per call.
- **Expect false positives even done well.** The trivialist design doesn't distinguish "has a
  relevant branch" from "has any branch at all" -- a verification pass built the same way inherits
  the same over-inclusiveness (harmless helper functions with no real branching will still get
  flagged), just surfaced as human-reviewed noise instead of silent bookkeeping. Probably an
  acceptable tradeoff (a short deduplicated list is cheap to skim), not a clean signal.

Not designed in detail yet -- proposed shape only.
