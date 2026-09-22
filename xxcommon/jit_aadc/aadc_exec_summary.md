# AadcExec

AADC (adjoint algorithmic differentiation) acceleration for Traitable computations. Builds and
caches AADC kernels per branch signature, keeping them valid across changing input values via
inline guard assertions, with instrumentation ("wrap every `if`, redirect eligible math calls")
handled automatically on import by `core_10x.callable_instrumentation`.

## Files

- `core_10x/callable_instrumentation.py` -- generic, theme-agnostic instrumentation facility.
- `xxcommon/jit_aadc/aadc_context.py` -- `AADCDomainSwap`, the session-scoped curve/root-solver swap.
- `xxcommon/jit_aadc/aadc_exec.py` -- the AADC theme: rewriter, kernel, exec, wiring.

## Import order matters

`aadc_exec.py` MUST be imported EARLY -- before any code defining or using the target
classes/modules. Its module-level `_registry.enable_auto_instrumentation()` only
affects modules imported *after* that point.

## `callable_instrumentation.py`

- `CallableRewriter(ast.NodeTransformer)` -- base class for a theme's per-function AST
  rewriter. `instrument(function)` extracts source, parses, visits (subclass-defined
  `visit_*`), recompiles, and re-executes against the function's own globals, binding
  whatever the subclass populated in `self.globals_to_bind`. One instance per theme, reused
  across every function it instruments. `location_id(node)` gives a `file:line` string.
- `InstrumentationRegistry` -- one instance per theme. Holds `known_module_names` (modules to
  instrument in full) and `target_base_classes` (default `{Traitable}` -- any subclass is a
  target regardless of its module).
  - `instrument_module(module)`: a known module gets every function and class instrumented
    unconditionally (nested classes included); an unknown module is searched recursively for
    classes matching `target_base_classes`, instrumenting only actual matches.
  - `instrument_class(cls)`: splits a class's own members into trait getters (routed to
    `instrument_getter`) and ordinary methods (routed to `instrument_method`); recurses into
    nested classes.
  - `instrument_getter(trait)`, `instrument_method(cls, method)`, `instrument_free_function(module, function)`:
    build the instrumented copy via `instrument_callable`, cache it, and register it for
    activation. Getters activate via a single global C++ flag
    (`Trait.set_edge_deps_tracking`); methods/functions activate via `setattr` swap.
  - `apply()`/`restore()`: toggle activation of everything already built. Do not build
    anything themselves.
  - `enable_auto_instrumentation()`/`disable_auto_instrumentation()`: install/remove a
    `sys.meta_path` hook (`InstrumentationFinder`/`InstrumentationLoader`) so newly imported
    modules get instrumented (built, not activated) automatically.

## `aadc_context.py`

`AADCDomainSwap` swaps two domain-specific implementations for AADC-aware ones for the duration of
an `AadcExec` session: curve interpolation (`CurveParams.DEFAULT_INTERPOLATOR`) and root-solving
(`xxfin.root_solver.root_scalar_impl`). Entered/exited once, by `AadcExec.__enter__`/`__exit__` --
not per kernel build. It does not patch `builtins`/`math.*` -- that's handled
per-instrumented-function by `AadcCallableRewriter`. The actual AADC recording session
(`aadc.record_kernel()`) is separate and genuinely per-build -- called directly in
`AadcKernel.build()`, not part of this class.

## `aadc_exec.py`

- `AadcCallableRewriter(CallableRewriter)` -- the AADC theme's rewriter. Wraps every `if` test
  in a call to `if_wrapper`; redirects every eligible `math.*`/`abs`/`min`/`max` call to
  `call_target`.
- `DefLocator` -- resolves a `file:line` to the dotted qualname of its innermost enclosing
  `def`, for naming the function in `raise_uninstrumented_warning`'s message.
- `raise_uninstrumented_warning(w)` -- raises a `RuntimeError` when a kernel build still
  produces an AADC passive warning despite instrumentation; means the registry
  (`known_module_names`/`target_base_classes`) has a gap.
- `AadcKernel` -- one recorded AADC kernel for one branch signature: builds under
  `record_kernel()`, perturbing discovered dependencies to `idouble` via `GraphDeps.perturb()`
  and keeping the `GraphDeps` instance; `eval`-time input resolution (`_resolve_inputs()`) reads
  each input's current value straight off its graph node via `GraphDeps.read()` -- a fresh
  per-call lookup, not a cached value or an override dict, so a plain `obj.trait = value` set on
  the same node between evals is picked up automatically.
- `AadcExec` -- the app-facing context manager for one `BoundTrait`.
  - `__enter__`/`__exit__`: `_registry.apply()`/`_registry.restore()` activate/deactivate
    already-instrumented code for the session; `AADCDomainSwap` is entered/exited once here too
    (curve interpolation/root-solving, session-scoped -- see `aadc_context.py` above).
  - `if_guard(guard_id, condition)` (classmethod, the AST-rewritten call target): during actual
    AADC recording, decodes the condition and registers an `aadc_assert` pinning it to its
    recorded outcome (this is what makes a stale kernel detectable later via
    `evaluate_kernel(...).errors.has_errors()`); outside recording, decodes and logs into
    `s_current_log` (a class-attribute `set`, scoped to one `create_kernel()` call) for
    signature computation.
  - `create_kernel()`: runs the bound trait once to build the dependency graph and the branch
    signature (via `if_guard()`'s logging) in the same call; on a cache miss, discovers input
    deps, perturbs them, records under `record_kernel()` (triggering `if_guard()`'s inline asserts),
    checks `passive_warnings()` (calls `raise_uninstrumented_warning` on any gap), and caches
    the kernel by signature.
  - `eval_kernel(kernel)`: replays the kernel; `has_errors()` means a guard's outcome changed
    since recording -- caller should call `create_kernel()` again for the current signature.
- Module-level: constructs the theme's `InstrumentationRegistry(AadcCallableRewriter(...))` and
  calls `enable_auto_instrumentation()` once, at import time.

## Known open points

- Whether `create_kernel()`'s post-staleness retry always records fresh or can hit an
  already-cached kernel for the new signature.
- Same `self.graph` is reused for `AadcExec`'s whole session, never reset between kernel
  builds.
