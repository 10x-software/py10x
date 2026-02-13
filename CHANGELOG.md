# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- **Rdate**: Business-day roll rules (preceding, following, modified preceding/following) and calendar-aware date utilities in `core_10x.rdate`
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
- Built-in caching system for trait values and entity state
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

- **0.1.12**: This package renamed: use **py10x-core** instead of `py10x-universe` in dependencies, CI, or local installs.
- **0.1.11**: C++ dependency renamed: use **py10x-kernel** instead of `py10x-core` in dependencies, CI, or local installs.
- **0.1.4**: Subclasses of `Traitable` must not override `__init__`; use `__post_init__` for customization. Python 3.10 no longer supported (3.11+ required). C++ packages are now `py10x-core` and `py10x-infra` (rename from core_10x_i / infra_10x_i if you referenced them directly).
- **0.1.2 and earlier**: Initial pre-release; no breaking changes from previous versions.


## Acknowledgments

- UI components based on Rio and Qt6 frameworks, focused on traitable editing and management
