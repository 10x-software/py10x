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
