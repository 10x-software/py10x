# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.6] - 2026-02-05

### Changed
- README image URL for PyPI compatibility
- OS compatibility tagging
- Invlusion of NOTICE

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
- **Package and branding**: C++ packages renamed to `py10x-core` and `py10x-infra` (from core_10x_i / infra_10x_i); email domain updates
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
- Initial pre-release of py10x-universe (10x Universe Ecosystem Core)
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
- C++ implementation: py10x-core, py10x-infra packages
- UI backends: Rio UI, PyQt6
- Infrastructure: pymongo
- Development: pytest, ruff, playwright

## [Unreleased]

### Planned
- Enhanced tests, documentation and examples
- Trait validation (automatic verification methods)
- Automatic resource management via enterprise backbone

---

## Version History

- **0.1.4**: Pre-release; AsOf, per-class stores, backbone/vault, TraitableHeir, env vars, rdate, testlib, lifecycle and trait-modification improvements
- **0.1.3**: Pre-release development version
- **0.1.2**: Pre-release development version
- **0.1.1**: Pre-release development version
- **0.1.0**: Initial development version

## Migration Guide

### From Development Versions

No migration from previous versions is necessary - package versions will automatically be updated when installing.

### Breaking Changes

- **0.1.4**: Subclasses of `Traitable` must not override `__init__`; use `__post_init__` for customization. Python 3.10 no longer supported (3.11+ required). C++ packages are now `py10x-core` and `py10x-infra` (rename from core_10x_i / infra_10x_i if you referenced them directly).
- **0.1.2 and earlier**: Initial pre-release; no breaking changes from previous versions.

## Contributors

- Sasha Davidovich <founders@10x-software.org>
- Ilya Pevzner (on behalf of 10X CONCEPTS LLC) <founders@10x-software.org>

## Acknowledgments

- Relies on py10x-core and py10x-infra packages containing the underlying C++ implementation
- UI components based on Rio and Qt6 frameworks, focused on traitable editing and management
