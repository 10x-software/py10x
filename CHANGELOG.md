# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2024-12-19

### Added
- Initial pre-release of py10x (10x Universe Ecosystem Core)
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
- Python 3.10+ support
- Core dependencies: numpy, python-dateutil, cryptography
- C++ implementation: core_10x_i, infra_10x_i packages
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

- **0.1.2**: Pre-release development version
- **0.1.1**: Pre-release development version
- **0.1.0**: Initial development version

## Migration Guide

### From Development Versions

No migration from previous versions is necessary - package versions will automatically be updated when installing.

### Breaking Changes

This is the initial pre-release, so no breaking changes from previous versions.

## Contributors

- Sasha Davidovich <founders@10x-software.org>
- Ilya Pevzner <founders@10x-software.org>

## Acknowledgments

- Relies on core-10x-i and infra-10x-i packages containing the underlying C++ implementation
- UI components based on Rio and Qt6 frameworks, focused on traitable editing and management
