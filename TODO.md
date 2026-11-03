# TODO

Known follow-up work that is not scheduled yet. Each item is a short summary; the linked issue has the details.

## Callable instrumentation

Fixes for both bugs are implemented on branches but not merged. Do the first before the second: after it, no user
code runs while instrumentation holds the lock.

- **Instrumented callables lose their original scopes** — added 2026-11-03,
  [#163](https://github.com/10x-software/py10x/issues/163), branch
  [`claude/instrument-without-exec`](https://github.com/10x-software/py10x/compare/main...claude/instrument-without-exec).
  The instrumented copy of a method breaks `super()`, closures and private names, and building it re-runs default
  expressions (a class-attribute default even fails the import).
- **Instrumentation is not thread-safe under concurrent imports** — added 2026-11-03,
  [#164](https://github.com/10x-software/py10x/issues/164), branch
  [`claude/instrumentation-lock`](https://github.com/10x-software/py10x/compare/main...claude/instrumentation-lock).
  Concurrent imports race on the shared rewriter and registry; fix is one lock, which must never be held while
  importing.
- **AADC session state is shared across threads** — added 2026-11-03,
  [#165](https://github.com/10x-software/py10x/issues/165). The guard log, the instrumentation switch and the math
  patching are process-wide, so concurrent sessions interfere.
- **Target re-walk can instrument a half-imported module** — added 2026-11-03,
  [#166](https://github.com/10x-software/py10x/issues/166). `set_target_base_classes()` may walk a module another
  thread is still importing and keep a stale method copy.

## From `ROADMAP.md`

- **Finish `runme_1st_app`** — added 2026-11-03, [#167](https://github.com/10x-software/py10x/issues/167). The
  first-run app stops short when authentication is needed and isn't installed as a command.
- **Replace `T.EMBEDDED` with the `embeddable` class flag** — added 2026-11-03,
  [#168](https://github.com/10x-software/py10x/issues/168). Embedding should be decided by the class, not a per-trait
  flag; touches serialization, `xx_fin` and the C++ kernel.
- **Use Basketable for parallelization** — added 2026-11-03,
  [#169](https://github.com/10x-software/py10x/issues/169). Planned, not started.
