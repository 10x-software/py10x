# Contributing to `py10x-core`

Thank you for your interest in contributing to `py10x-core`! This document provides guidelines for development, testing, and submitting contributions.

See also the [documentation map in README.md](README.md#documentation-map).

## Development Setup

**Prerequisites and platform-specific install commands:** [INSTALLATION.md](INSTALLATION.md).  
**Dev dependency profiles (`uv-sync`), constraints freeze, and releases:** [dev_10x/README.md](dev_10x/README.md).

`uv-sync` uses **dependency profiles** to decide where `py10x-core` and the C++ siblings (`py10x-kernel` / `py10x-infra`) come from. Choose the right one for your setup:

| Profile          | py10x-core     | C++ siblings (kernel/infra)         | When to use |
|------------------|----------------|-------------------------------------|-------------|
| `user`           | local editable | released wheels from PyPI           | No C++ compiler (or you don't want to build); you get published pre-releases only |
| `py10x-dev`      | local editable | git `main` (compiled locally)       | Most common dev case: pick up latest sibling changes from git without a local `../cxx10x` checkout |
| `py10x-core-dev` | local editable | local editable from `../cxx10x`     | You are making changes to the C++ packages in the sibling checkout (requires C++ toolchain) |

After cloning, a typical setup (middle-ground `py10x-dev` profile) looks like:

```bash
uv run --no-sync python -m dev_10x.uv_sync py10x-dev --all-extras
uv run --no-sync pytest
```

To **pick up the latest changes** from git-based siblings after pulling or when you want a refresh, e.g. after `git pull`

```bash
uv run --no-sync python -m dev_10x.uv_sync py10x-dev --all-extras --upgrade
```

**Important:** After the initial sync, always use `uv run --no-sync` (or the `uv-run` wrapper) for commands. Plain `uv run` can re-sync against `pyproject.toml` and accidentally fall back to PyPI-published siblings.

See [INSTALLATION.md](INSTALLATION.md#development-installation-recommended) for clone steps (including when and how to obtain the `../cxx10x` sibling) and [`dev_10x/README.md`](dev_10x/README.md) for the full profile table, reinstall rules, `XX_UV_INCREMENTAL`, and other options.

## Development Workflow

### Code Style

The project uses `ruff` for linting and formatting:

```bash
# Check for issues
uv run --no-sync ruff check .

# Auto-fix issues where possible
uv run --no-sync ruff check --fix .

# Format code
uv run --no-sync ruff format .
```

### Testing

#### Running Tests

`infra_10x/unit_tests/` requires MongoDB — see [INSTALLATION.md § Optional Database Dependencies](INSTALLATION.md#optional-database-dependencies). `core_10x` and `ui_10x` tests do not.

```bash
# Run all unit tests (with coverage by default)
uv run --no-sync pytest

# Run specific test suites
uv run --no-sync pytest core_10x/unit_tests/
uv run --no-sync pytest ui_10x/unit_tests/
uv run --no-sync pytest infra_10x/unit_tests/  # Requires MongoDB

# Manual tests are debugging scripts (run directly)
python core_10x/manual_tests/trivial_graph_test.py
python ui_10x/rio/manual_tests/basic_test.py
```

#### Test Structure

- `unit_tests/`: Automated unit tests with coverage
- `manual_tests/`: Debugging scripts for development and future test incorporation
- Tests use pytest framework with custom fixtures
- Coverage is enabled by default for all unit tests

#### Writing Tests

```python
from core_10x.traitable import Traitable, T

# Example unit test
def test_traitable_creation():
    
    class TestEntity(Traitable):
        name: str
        value: int
    
    entity = TestEntity(name="test", value=42)
    assert entity.name == "test"
    assert entity.value == 42
```

### Building
Normally builds are done by CI workflows. If you need to test a build manually, build with uv.
```bash
uv build
```

## Project Structure

High-level layout (build artifacts, `__pycache__`, and `dist/` omitted):

```
py10x/
├── core_10x/               # Core Traitable model, traits, dependency graph, stores
│   ├── unit_tests/         # Core unit tests (pytest + coverage)
│   ├── manual_tests/       # Direct-run debugging and exploration scripts
│   ├── testlib/            # Shared test fixtures, strict guards, history helpers
│   ├── code_samples/       # Standalone usage examples
│   ├── attic/              # Legacy/deprecated code (includes old backbone/)
│   ├── jit/                # JIT / accelerator experiments (numba, jax, cython)
│   ├── experimental/       # Early-stage work
│   └── *.py                # Core modules (traitable.py, resource.py, ...)
├── ui_10x/                 # UI components, trait editors, and backends
│   ├── rio/                # Rio web UI backend, widgets, components
│   │   ├── unit_tests/, manual_tests/, components/, widgets/
│   ├── qt6/                # Qt6 desktop backend
│   ├── unit_tests/
│   ├── examples/           # Interactive UI demos
│   └── ...
├── infra_10x/              # Storage and infrastructure
│   ├── mongodb_store.py, ibis_store.py, duckdb_store.py, ...
│   ├── unit_tests/         # Requires MongoDB (replica set)
│   └── testlib/
├── dev_10x/                # Developer tooling and release engineering
│   ├── uv_sync.py, uv_run.py   # Dependency profile management
│   ├── xx_promote.py           # Coordinated rc/prod releases + yanks
│   ├── constraints.py, xx_ci.py, xx_plan.py, ...
│   ├── pytest_plugin.py
│   └── unit_tests/
├── xx_common/              # Shared utilities (xxcalendar, curves, events, rdate, ...)
│   └── unit_tests/, manual_tests/
├── scripts/                # Helper scripts (e.g. cloud Mongo setup)
├── docs/                   # Supplementary docs (IP checklist, onboarding)
├── pyproject.toml          # Metadata, extras, scripts (uv-sync etc.), dev_10x config
├── constraints.txt         # Committed third-party dependency freeze
├── ruff.toml, pytest.ini,
└── ...
```

See also:
- [`dev_10x/README.md`](dev_10x/README.md) — dev profiles, `uv-sync`, `xx-promote`, CI gates
- Individual `*/unit_tests/` and package READMEs

## Submitting Changes

### Pull Request Process

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/your-feature-name`
3. **Make** your changes following the coding standards
4. **Add** tests for new functionality
5. **Run** the test suite: `uv run --no-sync pytest`
6. **Check** code style: `uv run --no-sync ruff check .`
7. **Commit** with descriptive messages
8. **Push** to your fork
9. **Create** a Pull Request

### Commit Messages

Use clear, descriptive commit messages:

```
feat: add new Traitable validation system
fix: resolve MongoDB connection timeout issue
docs: update README with installation examples
test: add unit tests for LineEdit widget
```

### Code Review

- All PRs require review from maintainers
- Address review feedback promptly
- Keep PRs focused and reasonably sized
- Update documentation for user-facing changes

## Coding Standards

### Python Code

- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Write docstrings for public APIs
- Use meaningful variable and function names

### Traitable Framework Development

See [GETTING_STARTED.md § Core Concepts](GETTING_STARTED.md#core-concepts) and
[§ Best Practices](GETTING_STARTED.md#best-practices) for the full framework guide. In brief:

- Use `Traitable` as the base class; never override `__init__` — use `__post_init__`
- Use `T()` / `RT()` / `T(T.ID)` per trait kind; implement `*_get` / `*_set` / converters as needed

### UI Component Development

The UI framework focuses on traitable editing and management:

- Use built-in editors like `CollectionEditor` for traitable collections
- Leverage `TraitableEditor` for individual traitable editing
- Focus on declarative user interfaces for traitable management

## Testing Guidelines

### Unit Tests

- Test public APIs thoroughly
- Include edge cases and error conditions
- Use descriptive test names
- Keep tests independent and isolated

### Integration Tests

- Test component interactions
- Verify storage integration (infrastructure layer)
- Test UI component behavior

### Manual Tests

- Use `manual_tests/` for debugging and development
- These are Python scripts run directly (not via pytest)
- Intended for future incorporation into unit tests
- Document expected behavior and setup instructions

## Documentation

### Code Documentation

- Document all public APIs
- Include usage examples
- Explain complex algorithms
- Update docstrings when changing APIs

### User Documentation

- Update README for new features
- Add examples for new functionality
- Keep installation instructions current

## Release Process (maintainers)

Versions come from git tags via setuptools-scm; releases are cut with `xx-promote`, not by hand-editing
`pyproject.toml`. See [dev_10x/README.md](dev_10x/README.md) (`xx-promote`, CI release gates) and
update [CHANGELOG.md](CHANGELOG.md) as part of the release.

## Getting Help

- Check existing issues and discussions
- Ask questions in GitHub Discussions
- Join our community on [Discord](https://discord.gg/m7AQSXfFwf) for discussion, support, and collaboration
- Contact maintainers for complex issues

## License

Contributions are subject to the project's license terms.

## Open Source & IP

For maintainers: before publishing or major releases, see [Open Source & IP Checklist](https://github.com/10x-software/py10x/blob/main/docs/OPEN_SOURCE_IP_CHECKLIST.md) for intellectual property and license compliance.
