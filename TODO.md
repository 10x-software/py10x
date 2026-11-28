# TODO

Known follow-up work that is not scheduled yet. Each item is a short summary; the linked issue has the details.

## Core

- **Finish `runme_1st_app`** — added 2026-11-03, [#167](https://github.com/10x-software/py10x/issues/167). The
  first-run app stops short when authentication is needed and isn't installed as a command.
- **Use Basketable for parallelization** — added 2026-11-03,
  [#169](https://github.com/10x-software/py10x/issues/169). Planned, not started.
- **Keyring allowlist refuses `ChainerBackend`** — added 2026-11-03,
  [#171](https://github.com/10x-software/py10x/issues/171). `xx-user-init` fails on a Linux desktop where two native
  keyring backends are viable.
- **A store query for `None` returns `XNone` rows** — added 2026-11-04,
  [#172](https://github.com/10x-software/py10x/issues/172). `None` is a value a getter returns and can't be saved;
  `XNone` is written as null, so a stored null is never `None`. Memory tells them apart, but both filters produce the
  same store query. Proposed fix: make `Trait.serialize_value(value, replace_xnone=True)` raise on `None`, mimicking
  the `undefined value` error that `BTraitable::serialize_traits` raises when saving. In-memory `eval` and searching
  a list or set trait for a `None` item are unaffected. To decide: raise, or match nothing on the store, where
  `existing_instances_by_filter` also checks objects in memory.
- **String filter on an `Any` trait matches a stored number** — added 2026-11-04,
  [#173](https://github.com/10x-software/py10x/issues/173). `f(v='10')` matches a stored `10` on DuckDB and Postgres
  but not on Mongo; it probably should not match on any store. Proposed fix: require `Any` traits
  to be runtime (`RT`), so they are never stored or filtered on a store.
- **Non-ASCII filter values never match on DuckDB** — added 2026-11-04,
  [#174](https://github.com/10x-software/py10x/issues/174). List item, whole-list, dict and `Any` filters with a
  non-ASCII value find nothing, because the filter's JSON literal is ASCII-escaped. Proposed fix: `ensure_ascii=False`
  in `IbisCollection._json_literal`, which made all four match in a trial patch.
- **Scopes leak out of suspended generators and coroutines** — added 2026-11-16,
  [#177](https://github.com/10x-software/py10x/issues/177). A scope block that spans a `yield` or `await` stays on the
  thread's stack while the frame is suspended, so the caller or another asyncio task runs inside it. Documented as a
  usage rule for now. Options: detect it in debug mode, or support it on Python 3.12+ with `sys.monitoring`.
- **`XX_GRAPH_ON` applies to the importing thread only** — added 2026-11-16, [#178](https://github.com/10x-software/py10x/issues/178). `core_10x` enters
  `GRAPH_ON()` on import, so other threads start off graph. For consistency every thread should start on graph. A
  trial made the default processor type on-graph for all threads (`BTraitableProcessor::set_default_type`, bound to
  Python) and was reverted:
  - A private cache per thread made objects created in one thread unusable in another ("origin cache is not
    reachable") and leaked each thread's cache on exit: nothing frees a thread's default processor.
  - One shared graph cache lets two threads compute the same node: the GIL can switch inside the Python getter, and
    the second thread clears the first one's recorded children and getter guard. A setter in another thread during
    the computation can leave a stale value marked valid.

  Proposed: a cache per thread over the shared default cache, with explicit `export_nodes()` to publish results to
  the shared cache, plus a fix for objects crossing threads. Needs a node "being computed" state if the graph is ever
  shared.
- **Free-threaded Python** — added 2026-11-16, [#179](https://github.com/10x-software/py10x/issues/179). Not supported; likely a large change. The kernel relies
  on the GIL: process-wide state (`XCache::default_cache()`, `BProcessContext::PC` flags, `s_default_type`, class
  registries), caches and graph nodes shared between threads, and Python-side globals (the store resource stack,
  `Scenario.s_instances`, `s_storage_helper_cached`, the instrumentation registry). The pybind11 module would also
  have to declare `py::mod_gil_not_used()`. Urgency is low: `requires-python` stops before 3.14, free-threaded builds
  are opt-in and not the default even in 3.14, and an extension that doesn't declare support re-enables the GIL in
  them. Revisit when adding 3.14 support or when a user needs parallel threads.
- **Re-entering a processor that is already on the stack** — added 2026-11-16,
  [#180](https://github.com/10x-software/py10x/issues/180). `begin_using()` pushes it again: below the top it drops the
  scope in between without reparenting; on top it hides who manages the scope. Proposed: always raise. Production code
  never re-enters; `AadcExec`, a `SaveIfChanged` test, two Rio tests and a nested anonymous `Scenario` would change.
- **`AsOfContext` applies to every thread** — added 2026-11-16,
  [#181](https://github.com/10x-software/py10x/issues/181). Its isolated cache is per thread, but its as-of helpers are
  set on classes, so other threads read historical data and leave it in the shared cache. Proposed: a thread-local
  stack of active contexts, from which the storage-helper descriptor derives and caches the helpers.
- **`verify()` is skipped for a new object on which nothing was set** — added 2026-11-26, issue not filed yet.
  `BTraitable::verify()` returns success while the object is still marked `LOAD_REQUIRED`, and `save()` verifies
  before it finds out that the object is not in the store. So a new object built from its ID traits alone is written
  with no verifier, no `NOT_EMPTY` check and no `post_verify` run. Reading any ordinary trait first makes the checks
  run. To decide: resolve the lazy state before verifying in `StorableHelper.save`, or verify again once the object
  turns out to be new.
- **`T.READ_ONLY`: what is left** — added 2026-11-28, issue not filed yet. The kernel now enforces the flag: no set in
  the scope the object lives in, a what-if value allowed in a scope below, and no loading (see `CHANGELOG.md`). Left
  open: `raw_set_value` goes around the check and can still set such a trait, until the value is invalidated; a
  what-if value saved from a scope below lands in the stored copy that a store searches by, by decision, and nothing
  warns of it; and nothing is refused when the class is defined for combinations that cannot work or were not tried: a
  `READ_ONLY` trait with a custom setter (called only for a what-if), with a `T.TS_TIME` / `T.TS_USER` flag (the store
  sets its stamp back after a save), or with `T.ID` and no getter (the constructor can no longer be given the value).

## Callable instrumentation

- **Instrumented callables lose their original scopes** — added 2026-11-03,
  [#163](https://github.com/10x-software/py10x/issues/163). The instrumented copy of a method breaks `super()`,
  closures and private names, and building it re-runs default expressions (a class-attribute default even fails the
  import). Postponed: the candidate fix, which avoids `exec`, needs more review.
- **Instrumentation is not thread-safe under concurrent imports** — added 2026-11-03,
  [#164](https://github.com/10x-software/py10x/issues/164). Concurrent imports race on the shared rewriter and
  registry state. Postponed: the candidate fix, a global lock, was not accepted; a better approach is needed.
- **AADC session state is shared across threads** — added 2026-11-03,
  [#165](https://github.com/10x-software/py10x/issues/165). The guard log, the instrumentation switch and the math
  patching are process-wide, so concurrent sessions interfere.
- **Target re-walk can instrument a half-imported module** — added 2026-11-03,
  [#166](https://github.com/10x-software/py10x/issues/166). `set_target_base_classes()` may walk a module another
  thread is still importing and keep a stale method copy.
