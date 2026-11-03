# TODO

Known follow-up work that is not scheduled yet. Each item says what is wrong, where it stands, and what is left.

## Callable instrumentation (`core_10x/callable_instrumentation.py`)

Both fixes are implemented and tested on their own branches, but not merged. Do 1 before 2: once instrumentation
runs no user code, the lock in 2 is safe to hold.

### 1. Build instrumented callables without `exec`

- **Branch:** [`claude/instrument-without-exec`](https://github.com/10x-software/py10x/compare/main...claude/instrument-without-exec)
  (`13ef55e`); tests in `core_10x/unit_tests/test_instrumentation_rebuild.py`.
- **Problem:** `CallableRewriter.instrument()` recompiles the rewritten `def` as a top-level statement, `exec`s it in
  the defining module's globals, then restores the name. The copy loses the scopes the `def` was written in, and
  building it runs code:
  - zero-arg `super()` fails: `RuntimeError: super(): __class__ cell not found`;
  - closure variables become globals: `NameError`, or `SyntaxError` for `nonlocal`;
  - private names are not mangled: `AttributeError` on `self.__x`;
  - a default that refers to a class attribute (`def m(self, x=SCALE)`) raises `NameError` at build time, which
    fails the import of the module being instrumented;
  - every default expression is evaluated again: user code runs during instrumentation, and the copy gets new
    default objects;
  - the module's binding for the function's name is briefly replaced, visibly to other threads.
- **Fix on the branch:** compile the `def` inside a stand-in for its original scopes (an outer function whose
  parameters are the free variables, plus the innermost enclosing class), then build the copy with
  `types.FunctionType` from the original's globals, defaults and closure cells. Nothing is executed. If the rebuilt
  code needs other free variables than the original, the function is left uninstrumented, as for a decorated one.
- **Behavior change:** the copy shares default objects and closure cells with the original.
- **Status:** full `core_10x` + `xxcommon` suites pass on 3.13; the new tests also pass on 3.11 and 3.12 (with the
  kernel stubbed). Merges cleanly onto `main` at `f8a1395`.
- **Exposure today:** low. No getter in `xx_fin` uses `super()` or private names; `__init_subclass__` in
  `xx_fin/xxfin/mkt_quotable.py` uses `super()` and would break only if a subclass were created during an AADC
  session.

### 2. Serialize instrumentation with one lock

- **Branch:** [`claude/instrumentation-lock`](https://github.com/10x-software/py10x/compare/main...claude/instrumentation-lock)
  (`f18dfdf`); tests in `core_10x/unit_tests/test_instrumentation_concurrency.py`.
- **Problem:** Python's import locks are per module, so the loader instruments concurrently imported modules in
  parallel, and nothing guards the shared state:
  - the one `CallableRewriter` per theme keeps the current filename on `self`, so a concurrent `instrument()` can
    put another file's name into guard ids;
  - two builds of the same name (`A.value`, `B.value`) `exec` into the same module globals: one gets the other's
    function, a stray global is left behind, or `KeyError` (goes away with 1);
  - `apply()`/`restore()` iterate `instrumented_callables` while an import adds to it:
    `RuntimeError: dictionary changed size during iteration`.
- **Fix on the branch:** one module-level `threading.RLock`, shared by every registry and rewriter (rewriters of
  different themes build into the same module globals), around `CallableRewriter.instrument()` and every registry
  method that touches registry state. `set_target_base_classes()` and `set_exclude_classes()` resolve names before
  taking it.
- **Rule: never import while holding the lock.** The loader runs under the importing module's own import lock and
  then takes ours; a thread that holds ours and imports that same module takes them in the opposite order. That
  deadlocks two threads (reentrancy doesn't help), and Python's import deadlock detection can't see our lock. A test
  covers it. After 1, the only code under the lock that isn't ours is metaclass hooks on non-Traitable targets.
- **Status:** suites passed on 3.13. Conflicts with 1 in `instrument()`: rebase onto 1 after it merges. Makes the
  `ContextVar` in [10x-software/py10x#129](https://github.com/10x-software/py10x/pull/129) unnecessary. #129's issue 4
  is covered by the re-walk on `main` plus the locked target-set update on this branch, and its issue 3 is not a
  real bug (`issubclass(cls, ())` returns `False`), so #129 can be closed.
- **Rejected alternatives:**
  - a `ContextVar` for the filename: covers only that race;
  - patching `importlib._bootstrap._ModuleLock` to be our lock: brings back a global import lock (import-time code
    that waits on a thread which imports hangs), relies on private API, and loses `_DeadlockError`.
  - If imports under the lock ever become necessary, have the loader only queue loaded modules, and instrument the
    queue under the lock in `apply()` and `set_target_base_classes()`.

### Related, not started

- **Run-time state shared across threads** (`xxcommon/jit_aadc/aadc_exec.py`):
  - `AadcExec.s_current_log` is one class-level slot: concurrent `new_kernel()` calls mix guard logs or hit
    `frozenset(None)`;
  - `BTrait::s_use_instrumented_getters` (`cxx10x/core_10x/btrait.h`) and `apply()`/`restore()` are process-wide:
    one thread leaving a session strips another's instrumentation mid-recording;
  - `AADCDomainSwap` patches `math.*` and `min`/`max`/`abs` for the whole process during recording.
  - Direction: the guard log in a `ContextVar`, the getter switch in the C++ `ThreadContext`, and session counting
    (or permanently installed instrumented methods) instead of `apply()`/`restore()` swapping.
- **Half-imported modules:** `set_target_base_classes()` also re-walks modules that another thread is still
  importing. If such a module reassigns a method after the walk, `apply()` installs a copy of the old one.

## From `ROADMAP.md`

Not done yet, checked against `main` at `f8a1395`. The other roadmap items are implemented but not marked done
there: `Traitable.existing_instances_by_filter()`, `T.STICKY` (= `OFFGRAPH_SET`), the `embeddable` class flag,
`NamedCallable`, `ClassTrait`, Basketable, and the `xx-*` command line utilities.

### Finish `runme_1st_app` (Automatic Resource Access with Authentication)

- `core_10x/apps/runme_1st_app.py` stops short:
  - when the main store requires authentication, it tells the user to run an "add_vault" utility that doesn't exist
    (the vault code points to `user_init`, i.e. `xx-user-init`), then exits;
  - the per-class store check (`EnvVars.var.use_ts_store_per_class`) loads `NamedTsStore.load_many()` into an unused
    variable and ends there (the `F841` exemption in `ruff.toml` hides this);
  - it isn't registered in `[project.scripts]` like the other apps.

### Replace `T.EMBEDDED` with the `embeddable` class flag

- Roadmap: a traitable is saved inside the containing object if its class is embeddable, externally otherwise.
- The class flag exists (`Traitable.s_embeddable`, `__init_subclass__(embeddable=...)`), but `T.EMBEDDED` is still
  used 24 times in 13 Python files: serialization in `core_10x/concrete_traits.py`, `core_10x/basket.py`
  (`bucketizers`), `core_10x/trait.py`, the `xx_fin` curves (`py_rate_curve.py`, `ir_zero_rate_curve.py`,
  `fx_forward_curve.py`) and tests. The flag itself is `BTraitFlags::EMBEDDED` in `cxx10x/core_10x/btrait.h`, so
  removing it changes `py10x-kernel`, a separately released package.

### Use Basketable for parallelization

- Roadmap: Basketable is "also planned to be used in parallelization". Nothing uses it for parallel work yet.
