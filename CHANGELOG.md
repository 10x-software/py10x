# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-05-17

### Added
- **`EventBase`** (`core_10x/traitable.py`): new base class for event-like traitables with `_at` (timestamp) and `_who` (authenticated user) traits that are populated server-side on `save()`. `TraitableHistory` now inherits from `EventBase`; `keep_history` is no longer required on `TraitableHistory` subclasses (it is inherited). Custom event collections can extend `EventBase` directly to get the same server-populated field behavior.
- **Forward references to sibling `Traitable` classes**: bare string annotations (e.g. `peer: "Peer" = T()`) are now resolved lazily — when the referenced class is defined later in the same module or in a sibling module, the placeholder is patched automatically. Composite forms (`list["Peer"]`, `Optional["Peer"]`, etc.) still require the name to be defined earlier; only bare identifiers can be deferred.
- **`NamedResource` bundle** (`core_10x/traitable.py`): a `Bundle` that associates a logical name with a resource URI and retrieves the live resource instance (with vault credentials when available). `NamedTsStore` is a built-in subclass mapping a name to a `TsStore` URI; used by the per-class store resolution mechanism.
- **Vault and credential management** (`core_10x/traitable.py`, `core_10x/vault_utils.py`, `core_10x/sec_keys.py`): `Traitable.store_from_uri(uri)` and `Traitable.vault_store()` now resolve credentials from the vault automatically — RSA-2048 encrypted per-user resource accessors (`VaultResourceAccessor`) are decrypted on-the-fly using the master password from the OS keyring, so no plaintext passwords appear in code or environment variables. Documented in `GETTING_STARTED.md` and `docs/USER_ONBOARDING_AUTH.md`.
- **User onboarding CLI tools** (`core_10x/apps/`): three new entry points registered in `pyproject.toml`: `xx-user-init` (self-registration), `xx-user-status` (health check for all registered resource accessors), and `xx-admin-save-user-credentials` (encrypt and store a resource password for a named user using only their public key).
- **URL support for test store** (`core_10x/testlib/test_store.py`): `TestStore` can now be initialized from a URI string, matching the interface of production stores.
- **`RC` supports `sum()` builtin** (`core_10x/rc.py`): `__radd__` now handles `other == 0` so `sum([rc1, rc2, rc3])` aggregates a list of `RC` results without needing an explicit starting value.
- **Environment variables** (`core_10x/environment_variables.py`):
  - **`AssertVar` removed, replaced by `EnvVars.var.<name>`** — the attribute returns a `Var` wrapper with `.value`, `.attr_name`, boolean truthiness, and `.check(predicate=None, err='is not defined')` that raises **`ValueError`** (previously `AssertionError` from `EnvVars.assert_var.<name>`) on missing or predicate-failing values. New helpers `EnvVars.create_var_name(env_name, attr_name)` and `EnvVars.var_name(var_or_name)` compute the `XX_`-prefixed env var name from a `Var` or attribute name.
  - **New env vars**: `XX_GRAPH_ON` (enter `GRAPH_ON()` at process start), `XX_LOG_TS_STORE_URI` (Mongo URI for `LOG` persistence — stdout-only when unset), `XX_USE_TS_STORE_TRANSACTIONS` (wrap multi-save operations in TsStore transactions; used by `Traitable._transaction_ctx`, `SaveIfChanged`, history saves, and `save(save_references=True)`).
  - **Value coercion hardened**: the `bool`, `int`, and `float` converters now wrap `ast.literal_eval` in the declared type, so e.g. `XX_USE_TS_STORE_TRANSACTIONS='1'` yields `True` (a `bool`) rather than `1` (an `int`). Empty or unparseable strings raise `TypeError` for numeric/boolean variables. Covered by `core_10x/unit_tests/test_environment_variables.py::test_env_vars_converts_bool_true`.
  - **`vault_uri` default**: `XX_VAULT_URI` resolves via `vault_uri_get` to `XX_MAIN_VAULT_URI` when unset.
  - **Documentation**: new `## Configuration` section in `GETTING_STARTED.md` describes the `EnvVars` facility (declaration, supported types, `*_get` / `*_apply` hooks, `Var.check()` idiom, required-variable patterns) and lists every built-in `XX_*` variable with type, default, and purpose; pre-existing scattered references (`XX_MAIN_TS_STORE_URI`, `XX_USE_TS_STORE_TRANSACTIONS`, `XX_LOG_TS_STORE_URI`) now link to it.
- **`SaveIfChanged` context manager** (`core_10x/ts_store.py`): auto-saves any `Traitable` whose trait values are assigned inside the `with` block. The yielded tracker exposes `tracked_objects()`. An optional sequence of `Traitable` classes restricts which tracked objects are saved via an `isinstance` check (so subclasses of any listed class are saved as well; non-storable classes raise `RuntimeError`). When `EnvVars.use_ts_store_transactions` is enabled (`XX_USE_TS_STORE_TRANSACTIONS=1`), one transaction per distinct store is opened so that a failing `save()` rolls back all saves in the block atomically. Docs added to `GETTING_STARTED.md`; store-agnostic tests in `core_10x/testlib/ts_store_transaction_tests.py::TestSaveIfChanged` (exercised by `core_10x/unit_tests/test_ts_store.py` and `infra_10x/unit_tests/test_mongo_db.py`).
- **`GraphDeps`** (`core_10x/exec_control.py`): runtime dependency introspection under `GRAPH_ON`. Given a bound trait (`instance.T.trait_name`) as the root node, a target `Traitable` class, and zero-or-more trait names, `GraphDeps` queries the live graph cache to find which instances of that class (and which of their traits) are successors of the root node. `deps()` iterates discovered dependencies as `(cls, obj, trait, value)` tuples; `perturb()` / `perturb_value()` overwrite a cached graph node directly, enabling perturbation-style sensitivity calculations. `Cls.T.trait_name.trait` (or equivalently `Cls.T('trait_name')`) obtains a raw `Trait` for use with `perturb()`; in the typical loop pattern the trait comes directly from `deps()` so no separate lookup is needed. Designed to be subclassed: domain-specific wrappers encode a default `target_class` and read default trait names from a class-level `s_leaf_trait_names` set, so call-sites need only pass the root `BoundTrait`. Docs added to `GETTING_STARTED.md`; tests in `core_10x/unit_tests/test_graph_deps.py`.
- **`_update` constructor parameter and `new_or_update` class method** (`core_10x/traitable.py`, `cxx10x/core_10x/btraitable.cpp`): `_update=True` (and the `Cls.new_or_update(**kwargs)` convenience wrapper) allows non-ID traits to be set during traitable construction while **preserving** all existing non-ID trait values that are not explicitly provided. This is the partial-update counterpart to `_replace=True` / `new_or_replace`, which resets unspecified non-ID traits to `XNone`.
- **Basket / Bucket facility** (`core_10x/basket.py`): composable containers for `Traitable` objects with optional multi-level bucketing (`Bucketizer`: `by_class`, `by_feature`, `by_range`, `by_breakpoints`), trait lifting via `aggregator_class`, incremental `add_bucketizer`, and the `Basketable` mixin for recursive `contents()` into a target `Basket`. `reset_members_on_set_bucketizers` trait (default `True`) controls whether assigning `basket.bucketizers` clears existing members (`True`, the safe default) or re-sorts them into the new bucket scheme (`False`).
- **NamedCallable** (`core_10x/named_constant.py`): subclass of `NamedConstant` for named functions — each member wraps a callable, callable by name (`Aggregator.SUM(items)`); `NamedCallable.just_func(f)` wraps an anonymous callable.
- **`ClassTrait`** (`core_10x/trait.py`): a `NamedCallable` subclass that wraps a single `Trait` of a `Traitable` class as a named, serializable callable — `ClassTrait(instance)` returns the trait value, equivalent to `lambda obj: obj.trait_name` but with identity, a `.cls` reference, and round-trip serialization to `[class_id, trait_name]`. Returned by `Cls.T.trait_name` (class-level `.T` accessor); used wherever a `NamedCallable` feature-extractor is expected (e.g. `Bucketizer.by_feature`, aggregators, pipeline slots). Distinct from `Cls.T('trait_name')`, which returns the raw `Trait` object (a `BTrait`). Docs added to `GETTING_STARTED.md`; tests in `core_10x/unit_tests/test_traitable.py`.
- **`NamedConstantValue` / `NamedConstantTable`** (`core_10x/named_constant.py`): map named constants to associated values (`NamedConstantValue`) or to rows of values keyed by a second constant class (`NamedConstantTable`); `NamedConstantTable.extend(subclass, ...)` adds rows from a subclass without mutating the original table. `NamedConstant.item(symbol_name)` looks up a constant by string name.
- **`core_10x/rel_db.py`**: relational-style DB helpers and tests.
- **`core_10x/scenario.py`** — `Scenario`: a named scope in which trait values (set and computed) are cached and isolated from other scenarios; computed traits are dependency-tracked within the scope.  Named scenarios are singletons — `Scenario('name')` from anywhere in the codebase always returns the same instance and resumes the same cached scope.  Anonymous `Scenario()` creates a fresh scope each time, discarded on exit.  Nested scenarios inherit set values from their parent.  Docs and tests added.
- **`core_10x/logger.py`**: logging helpers including **PerfTimer**.
- **`core_10x/xinf.py`**: extended infinity helpers for range/bucket specs; public API is **`XInf`** and **`-XInf`** (negative infinity).
- **`xx_common` package**: calendar, business-day **rdate**, and **curve** moved out of `core_10x` (see *Changed* / migration).
- **`infra_10x/testlib/`**: shared Mongo collection helpers for tests.
- **GitHub Actions**: reusable **MongoDB replica set** setup action; CI workflow and dependabot updates.
- **`ROADMAP.md`**, **`AGENTS.md`**: project/agent guidance updates.

### Changed
- **`Self` return types on `Traitable` methods** (`core_10x/traitable.py`): constructor-like and fluent methods now declare `-> Self` where applicable, giving IDEs accurate type information without losing subclass specificity.
- **Canonical resource URI with default port** (`core_10x/resource.py`): resource URIs are now normalized to include an explicit default port, giving a single canonical form across connection scenarios.
- **`T.EMBEDDED` is now optional**: traits that hold an embeddable `Traitable` type no longer need to be explicitly marked `T.EMBEDDED` — serialization detects and embeds them automatically. Traits that *are* marked `T.EMBEDDED` enforce that every stored value is a fully embedded object; traits *without* the flag accept both fully and partially embedded values.
- **`T.STICKY`** (alias `BTraitFlags.OFFGRAPH_SET`): when a getter computes a value while the object is in off-graph mode the result is automatically written back to the trait slot, so subsequent reads return the cached value without re-running the getter. This is the right flag for mutable container traits (such as bucket lists) that need to hold state across calls without participating in the dependency graph.
- **`Traitable` value-access methods** (py10x-kernel + py10x-core): overloaded `get_value` / `set_value` / `raw_set_value` / `invalidate_value` / `is_valid` replaced by statically dispatched pairs — name-based variants keep their original names; `Trait`-object variants are renamed with a `_trait_` infix (e.g. `get_trait_value`, `set_trait_value`). `*_with_args` suffixed variants replace the `*args` overloads. See *Breaking Changes* for the full mapping.
- **`core_10x/ts_store.py`**, **`core_10x/ts_union.py`**, **`core_10x/resource.py`**, **`core_10x/nucleus.py`**: store/resource refactoring and transaction support.
- **UI** (`ui_10x`): `traitable_editor`, `table_view` / `table_header_view`, `utils`, `concrete_trait_widgets`, Qt tables, macOS commit filter, Rio line-edit test tweak; new/updated examples (**`price_simulator`**, **`guess_word`** refresh).


### Fixed
- **`IN` filter operator** (`core_10x/trait_filter.py`): `IN(values)` now also accepts a `set`, in addition to `list` and `tuple`, as the values argument.
- **`trait_filter.py` inner-filter class leak**: `traitable_class` set on an outer filter was incorrectly overriding the `traitable_class` of any nested inner filter; each filter sub-expression now retains its own class context.
- **Bundle / history interaction** (`core_10x/traitable.py`): history records for bundle members are now written to each member's class-specific collection rather than the shared bundle base collection; fixes a crash when a history-keeping member was saved through a bundle.
- **`Traitable.is_bundle`** corrected to return `True` only for bundle base classes and bundle members, not for unrelated traitables that happened to share collection names.
- **Storage helper sharing bug** (`core_10x/traitable.py`): subclasses were written to the wrong collection when a superclass's storage helper was read or written first; each class now keeps its own helper instance.
- **MongoDB utils for non-standard ports** (`infra_10x/mongodb_utils.py`, `infra_10x/mongodb_admin.py`): connection strings with explicit non-default ports are now parsed and forwarded correctly.
- **Admin vault workflow** (`core_10x/apps/admin_save_user_credentials.py`): the admin flow no longer attempts to decrypt a user's private key (it does not have access to it); a Resource Accessor for the vault host is now auto-saved so that other databases on the same host become accessible without additional setup steps.
- **`curve.value` float coercion** (`xx_common/curve.py`): `curve.value` now always returns a `float`; previously it could return an `int` or `numpy` scalar in edge cases.

## [0.1.14] - 2026-02-14

### Added
- **Open source release:** Repository opened for public access; `py10x-core` and documentation are available under the MIT License.

### Changed
- **README:** Overhauled for clarity and first-time visitors: value proposition, Hello World with shared-identity example, "When to use" and "How is this different" sections, and full GitHub links throughout. Removed redundant licensing/architecture block; LICENSE and NOTICE remain the source of truth.

## [0.1.13] - 2026-02-13

### Fixed
- **Windows tests**: Fixes and skips for tests that were failing on Windows (traitable history tests, infra mongo history, UI Rio internals).
- **History**: Fix history bug in traitable/store logic; traitable history tests made more robust.

### Changed
- **Licensing:** **py10x-kernel** and **py10x-infra** are now open source (MIT). README, NOTICE, and `docs/OPEN_SOURCE_IP_CHECKLIST.md` updated accordingly; the full platform (py10x-core + py10x-kernel + py10x-infra) is fully open source.

## [0.1.12] - 2026-02-12

### Changed
- **Package rename:** This package is now **py10x-core**. Updated throughout: `pyproject.toml`, README, NOTICE, docs, and code references.

## [0.1.11] - 2026-02-11

### Added
- **uv-sync installable command**: `uv_sync` available as an installable CLI command when using dev_10x.

### Changed
- **C++ package rename**: The native C++ dependency is now **py10x-kernel**. Updated throughout: `pyproject.toml`, README, NOTICE, docs, and code references; license URL now `py10x_kernel`.
- **dev_10x.uv_sync**: Reduced verbosity; avoids unnecessary rebuilds; re-exec on Windows for correct environment; improved behavior when locating `pyproject.toml` (checks current directory).
- **dev_10x.uv_sync**: Fixed info message for user profile.
- **Documentation**: README updates and merged redundant sections.

## [0.1.10] - 2026-02-09

### Added
- **Dynamic versioning**: Version read from `dev_10x.version`; `core_10x`, `infra_10x`, and `ui_10x` expose `__version__` with fallback when `dev_10x` is not installed.
- **dev_10x.uv_sync**: Profile-based `uv sync` helper (e.g. `user`, `domain-dev`, `py10x-dev`, `py10x-core-dev`) that injects `[tool.uv.sources]` for `py10x-core`, `py10x-kernel`, and `py10x-infra` from git or local paths.
- **Version tests**: `core_10x/unit_tests/test_version.py` and `infra_10x/unit_tests/test_version.py` assert package versions are set (no `0.0.0` or `unknown`).

### Changed
- **Documentation links**: Git and doc references updated from `10X-LLC` to `10x-software`; GETTING_STARTED, INSTALLATION, README, and CONTRIBUTING use full GitHub URLs where appropriate.
- **C++ dependency constraints**: Relaxed from exact (`==0.1.9`) to `>=0.1.9,<0.2.0` to allow minor non-breaking releases.
- **Build**: `pyproject.toml` uses `dynamic = ["version"]` and version-file; dev dependencies include `tomlkit` and `licensecheck`; package list includes `dev_10x`.

## [0.1.9] - 2026-02-08

### Added
- **Verifiers documentation**: GETTING_STARTED.md section “Verifiers (Validation on verify() and save())” describing `*_verify` methods, that they run only on `verify()` or `save()` (not on assignment), and examples.
- **Verifier tests**: `test_verify_success`, `test_verify_fails_when_verifier_returns_error`, `test_verify_not_called_on_set`, and `test_serialize_runtime_endogenous_reference` in `core_10x/unit_tests/test_traitable.py`.

### Changed
- **Trait**: `Trait` now uses a custom metaclass and `__slots__`; default `fmt` uses `t_def.fmt or trait.s_fmt`; `s_ui_hint` and `s_fmt` moved to class-level defaults.
- **pyproject**: Version set to 0.1.9; dependency pins for py10x c++ packages.

## [0.1.8] - 2026-02-06

### Added
- **Traitable.verify()**: Implemented using `BTraitable.verify_value(trait)`; checks `NOT_EMPTY` and per-trait `f_verify`; error header via `RC.prepend_error_header()`.
- **TsStore.populate()**: New method for server-side population of params (e.g. `_who`, `_at`) in serialized data; subclasses may override.

### Changed
- **Attic**: Unused code moved to `core_10x/attic/` (backbone, vault, data_domain, entity, package_manifest).
- Package and documentation refer to the pip-installable package as **py10x-core** (hyphen); repo path remains **py10x**.
- README: early-preview disclaimer; licensing/attribution and authors sections updated.
- CHANGELOG: version order (newest first), 0.1.7 and 0.1.8 entries.

## [0.1.7] - 2026-02-05

### Changed
- README image URL for PyPI compatibility
- OS compatibility classifiers (Windows, Linux, MacOS)

## [0.1.6] - 2026-02-05

### Changed
- OS compatibility tagging
- Inclusion of NOTICE

## [0.1.5] - 2026-02-05

### Changed
- README image URL for PyPI compatibility
- Development status classifier set to Beta
- CI: uv cache keyed by pyproject.toml; optional uv lock --upgrade step removed

## [0.1.4] - 2026-02-04

### Added
- **Traitable lifecycle**: `__post_init__` hook for subclass customization; overriding `__init__` is no longer allowed (use `__post_init__` instead)
- **Traitable updates**: `_replace` constructor parameter and `new_or_replace()` for updating non-ID traits of an existing entity by ID
- **AsOf context**: Time-travel queries for traitables that keep history; generalized to subclasses and all history-keeping traitable classes; graceful handling for classes that do not keep history
- **Per-class store association**: Different store (e.g. TsStore) per traitable class via ts-class association; `use_ts_store_per_class` and related configuration
- **TsStore / TsCollection**: Abstract store API; `TsStore` resource type, `TsUnion`; `store_class()` registration; `TsDuplicateKeyError`; collection `copy_to`
- **Backbone and vault**: `core_10x.backbone` (backbone_store, vault, namespace, bound_data_domain) and `core_10x.vault` (vault, vault_user, vault_traitable, sec_keys) for credentials and lightweight backbone
- **TraitableHeir**: Traitable that delegates trait values from a grantor traitable (`_grantor`); heir getters and serialization that omit unset grantor traits
- **Environment variables**: `core_10x.environment_variables` with typed env vars, classproperty getters, optional `*_apply` hooks, and `AssertVar` for required vars
- **Rdate**: Business-day roll rules (preceding, following, modified preceding/following) and calendar-aware date utilities in `xx_common.rdate`
- **NamedConstant**: `core_10x.named_constant` with `NamedConstant`, `NamedConstantTable`, and `cls.item(symbol_name)` lookup
- **Testlib**: Shared test utilities in `core_10x.testlib` (test_store, traitable_history_tests, ts_tests)
- **Trait modification**: Unset trait default in trait modification; support `None` as `flags_to_set` (clearer than `BFlags(0)`)
- **UI**: TraitableView omits hints with `widget_type` NONE; `collection_editor_app` in `ui_10x.apps`
- **AGENTS.md**: Meta-guide for AI agents and tools working in the repo (canonical docs, tooling, traitable invariants, test layout)

### Changed
- **Package and branding**: C++ packages renamed to `py10x_kernel` and `py10x_infra` (from core_10x_i / infra_10x_i); email domain updates
- **Python**: Requires Python 3.11+ (up to <3.13) per pyproject.toml
- **Rio UI**: Upgraded to Rio 0.12
- **Dependencies**: Version bumps for numpy, cryptography, pymongo, etc.; keyring and requests added where needed
- **Lint/format**: Ruff rules relaxed and applied consistently

### Fixed
- `existing_instance_by_id(_throw=False)` for runtime objects when instance does not exist (with C++ update)
- AsOf context exception handling when AsOf threw on enter (invalid BCP left on stack)
- Revision handling for immutable entities
- Rejection of unstable class names containing `__main__` or `<locals>`
- Filter serialization
- Runtime anonymous traitable traits no longer required to be embedded
- Runtime endogenous serialization and related checks (tests)
- Improved C++ exception traces

## [0.1.3] - (pre-release development)

No separate changelog; see Version History below.

## [0.1.2] - 2024-12-19

### Added
- Initial pre-release
- Core data modeling with `Traitable` framework
- Trait-based traitable definitions with type safety
- Object identification system (endogenous/exogenous traitables)
- Serialization and deserialization framework
- Storage integration with MongoDB store
- Cross-platform UI components focused on traitable editing (Rio and Qt6 backends)
- MongoDB integration via `infra_10x`
- Built-in Caching system for trait values and entity state
- Manual resource management using context managers
- Comprehensive test suite

### Core Features
- **Traitable Framework**: Traitable modeling with traits, validation, and persistence
- **Object Identification**: Endogenous traitables (with ID traits) share trait values globally by ID, exogenous traitables get auto-generated UUIDs
- **Dependency Graph**: Automatic computation of trait values and dependency tracking
- **Seamless UI Framework**: Cross-platform components with automatic framework selection
- **Storage Integration**: MongoDB store with revision tracking and flexible data persistence
- **Infrastructure**: Manual resource management (enterprise resource management planned for future release)

### UI Components
- Focused on traitable editing and management
- CollectionEditor for traitable collections
- TraitableEditor for individual traitable editing
- LineEdit, TextEdit, PushButton, Label
- Layout components (VBoxLayout, HBoxLayout, FormLayout)
- Dialog, MessageBox, GroupBox
- ListWidget, TreeWidget, CalendarWidget
- ScrollArea, Splitter, Spacer
- RadioButton, CheckBox, Separator

### Infrastructure
- Storage integration with MongoDB store
- Collection operations (CRUD, querying, indexing)
- Revision-based conflict resolution
- Manual resource management using context managers

### Dependencies
- Python 3.11+ support
- Core dependencies: numpy, python-dateutil, cryptography
- C++ implementation: our core and infra packages
- UI backends: Rio UI, PyQt6
- Infrastructure: pymongo
- Development: pytest, ruff, playwright

---

## Version History

- **0.2.0**: EventBase; forward refs for sibling Traitables; NamedResource bundle; user status util + onboarding guide; RC.sum(); Self return types; canonical resource URI; filter fixes (IN set, inner-class leak); bundle/history fix; is_bundle fix; storage sharing fix; MongoDB non-standard port fix; admin vault workflow fix; curve.value float fix; Basket/Bucket; NamedCallable/ClassTrait; NamedConstantValue/Table; rel_db, scenario, logger; xx_common split; infra/mongo and UI updates; test run from installed package; CI Mongo action
- **0.1.14**: Open source release; README overhaul (value prop, Hello World, when to use, full GitHub links)
- **0.1.13**: Windows test fixes; history bug fix and more robust traitable history tests; pyproject fix; docs updated
- **0.1.12**: This package rename to `py10x-universe` → `py10x-core`; docs updated
- **0.1.11**: C++ package rename `py10x-core` → `py10x-kernel`; `uv-sync` installable command; uv_sync verbosity/rebuilds/Windows/doc fixes
- **0.1.10**: Dynamic versioning (dev_10x), dev_10x.uv_sync, version tests; doc links to 10x-software; C++ deps relaxed to >=0.1.9,<0.2.0
- **0.1.9**: Verifiers docs and tests; Trait metaclass/slots and fmt handling; pyproject 0.1.9
- **0.1.8**: Traitable.verify(), TsStore.populate(), RC.prepend_error_header; attic move; entity_filter removed; naming (`py10x-universe`, `py10x-core`, `py10x-infra`); README disclaimer
- **0.1.7**: OS classifiers, README image URL
- **0.1.6**: NOTICE, OS tagging, README image
- **0.1.5**: Beta classifier, CI cache
- **0.1.4**: Pre-release; AsOf, per-class stores, backbone/vault, TraitableHeir, env vars, rdate, testlib, lifecycle and trait-modification improvements
- **0.1.3**: Pre-release development version
- **0.1.2**: Pre-release development version
- **0.1.1**: Pre-release development version
- **0.1.0**: Initial development version

## Migration Guide

### From Development Versions

No migration from previous versions is necessary - package versions will automatically be updated when installing.

### Breaking Changes

- **0.2.0**: Imports for **calendar / rdate / curve** moved from `core_10x` to the **`xx_common`** package (e.g. `xx_common.rdate`, `xx_common.curve`, `xx_common.xxcalendar`). Update any `from core_10x.…` references accordingly. **`core_10x.xinf`**: prefer **`-XInf`** for negative infinity in your code; **`MInf`** is internal to that module (`from core_10x.xinf import *` only exports **`XInf`**).
- **0.2.0 (py10x-kernel)**: The overloaded `get_value` / `set_value` / `raw_set_value` / `invalidate_value` / `is_valid` methods on `Traitable` — which previously accepted either a trait name (`str`) or a `Trait` object as their first argument — have been replaced by four statically-dispatched variants each:

  | Old (overloaded) | New — name-based | New — Trait-based |
  |---|---|---|
  | `get_value(name)` | `get_value(name)` | `get_trait_value(trait)` |
  | `get_value(name, *args)` | `get_value_with_args(name, *args)` | `get_trait_value_with_args(trait, *args)` |
  | `set_value(name, v)` | `set_value(name, v)` | `set_trait_value(trait, v)` |
  | `set_value(name, v, *args)` | `set_value_with_args(name, v, *args)` | `set_trait_value_with_args(trait, v, *args)` |
  | `raw_set_value(name, v)` | `raw_set_value(name, v)` | `raw_set_trait_value(trait, v)` |
  | `raw_set_value(name, v, *args)` | `raw_set_value_with_args(name, v, *args)` | `raw_set_trait_value_with_args(trait, v, *args)` |
  | `invalidate_value(name)` | `invalidate_value(name)` | `invalidate_trait_value(trait)` |
  | `invalidate_value(name, *args)` | `invalidate_value_with_args(name, *args)` | `invalidate_trait_value_with_args(trait, *args)` |
  | `is_valid(name)` | `is_valid(name)` | `is_trait_valid(trait)` |

  The name-based variants keep their original names; only the `Trait`-object variants are renamed. **`py10x-core` has been updated throughout** — this only affects code that called these methods directly (e.g. custom getters/setters, extensions) using a `Trait` object as the first argument.
- **0.1.12**: This package renamed: use **py10x-core** instead of `py10x-universe` in dependencies, CI, or local installs.
- **0.1.11**: C++ dependency renamed: use **py10x-kernel** instead of `py10x-core` in dependencies, CI, or local installs.
- **0.1.4**: Subclasses of `Traitable` must not override `__init__`; use `__post_init__` for customization. Python 3.10 no longer supported (3.11+ required). C++ packages are now `py10x-core` and `py10x-infra` (rename from core_10x_i / infra_10x_i if you referenced them directly).
- **0.1.2 and earlier**: Initial pre-release; no breaking changes from previous versions.


## Acknowledgments

- UI components based on Rio and Qt6 frameworks, focused on traitable editing and management
