# Contributing to `py10x-core`

Thank you for your interest in contributing to `py10x-core`! This document provides guidelines for development, testing, and submitting contributions.

See also the [documentation map in README.md](README.md#documentation-map).

## Development Setup

**Prerequisites and platform-specific install commands:** [INSTALLATION.md](INSTALLATION.md).  
**Build modes, constraints freeze, and releases:** [dev_10x/README.md](dev_10x/README.md).

A development checkout installs `py10x-core` editable together with the C++ packages built from this
repo ([`cxx10x/`](cxx10x/README.md): `py10x-kernel`, `py10x-infra`) and the in-repo downstream
fin-base (`xx_fin/`), so it needs a C++ toolchain. After cloning, from the repo root (bash; Git Bash on
Windows):

```bash
./xx-build init     # once: builds the C++ packages in order, then syncs everything from uv.lock
uv run pytest
```

From then on plain `uv sync` keeps the environment current (after a `git pull` or a dependency
change), and `uv run <command>` syncs before it runs. The C++ packages are editable and rebuild on
import: edits under `cxx10x/` take effect on the next import, with no re-sync.
`./xx-build init --clean` starts over.

**Build modes:** the default mode, `dev`, builds the C++ packages `Debug`, so you can step through
C++ in a debugger. That makes C++-heavy tests noticeably slower, especially on Windows. If test speed
matters more to you than debugging C++, switch to `Release`:

```bash
./xx-build set-mode dev-release   # Release, still rebuild-on-import
./xx-build show-mode              # the active mode
./xx-build set-mode dev           # back to Debug (its build dir is kept, so no rebuild from scratch)
./xx-build rebuild                # rebuild in the active mode, e.g. after toggling XX_CXX_SANITIZERS
```

CI, the Docker image and published wheels are Release (`ci-release`, and cibuildwheel).

**Leaving things out:** plain `uv sync` installs every default dependency group: core's extras
(`extras`) and fin-base (`test`, `test-extras`). Pass `--no-group extras` or
`--no-group test --no-group test-extras` to leave them out (core CI does the latter, so `xxfin` is not
importable there). Never run `uv sync --upgrade` / `uv lock --upgrade`: `uv.lock` changes only
through `xx-constraints compile` or the weekly refresh workflow.

`uv-sync` and `uv-run` are retired; see [`dev_10x/README.md`](dev_10x/README.md#uv-sync--uv-run--retired)
for what replaces each old invocation, and for the build modes and other options.

## Development Workflow

### Code Style

The project uses `ruff` for linting and formatting:

```bash
# Check for issues
uv run ruff check .

# Auto-fix issues where possible
uv run ruff check --fix .

# Format code
uv run ruff format .
```

### Testing

#### Running Tests

`uv run pytest` does **not** require a local MongoDB or PostgreSQL. Tests that need a
live store skip automatically when the server is unreachable (see `core_10x/testlib/strict.py` —
`need()` skips locally; under `XX_TEST_STRICT=1`, as in Linux CI, an unmet precondition fails
instead). Install Mongo and/or Postgres only if you want those tests to run locally — see
[INSTALLATION.md § Optional Database Dependencies](INSTALLATION.md#optional-database-dependencies).

Each pytest session gets its **own** database on each live backend and drops it at the end —
the `live_store` fixture (`core_10x/testlib/test_databases.py`), which also hands out the
stores. It is **requested, not autouse** and lazy per backend, so a run that never asks for a
store neither probes for a server nor creates anything. A session killed before teardown leaves
its database behind; [`xx-test-db-clean`](dev_10x/README.md) sweeps those.

```bash
# Run all unit tests (xdist: -n auto --dist loadscope via pytest.ini)
uv run pytest

# Run specific test suites
uv run pytest core_10x/unit_tests/
uv run pytest ui_10x/unit_tests/
uv run pytest infra_10x/unit_tests/  # postgres soft-skips if down; mongo matrix hard-fails if down

# Serial / pdb (disable xdist)
uv run pytest -n0 path/to/test_foo.py::test_bar

# Manual tests are debugging scripts (run directly)
python core_10x/manual_tests/trivial_graph_test.py
python ui_10x/rio/manual_tests/basic_test.py
```

#### Test Structure

- `unit_tests/`: Automated unit tests (parallel via pytest-xdist by default)
- `manual_tests/`: Debugging scripts for development and future test incorporation
- Tests use pytest framework with custom fixtures
- Coverage reports are configured in `pytest.ini`; enable measurement with `--cov` (intended for the nightly ASan lane)

#### Writing Tests

```python
from core_10x.traitable import Traitable, T


# Example unit test
def test_traitable_creation():

    class TestEntity(Traitable):
        name: str
        value: int

    entity = TestEntity(name='test', value=42)
    assert entity.name == 'test'
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
│   ├── mongodb_store.py, ibis_store.py, duckdb_store.py, postgres_store.py, ...
│   ├── unit_tests/         # live Mongo/Postgres stores (Postgres soft-skip; Mongo hard if listed)
│   └── testlib/
├── dev_10x/                # Developer tooling and release engineering
│   ├── xx_build.py             # ./xx-build: dev environment setup and build modes
│   ├── xx_promote.py           # Coordinated rc/prod releases + yanks
│   ├── constraints.py, xx_ci.py, xx_plan.py, ...
│   ├── pytest_plugin.py
│   └── unit_tests/
├── xxcommon/              # Shared utilities (xxcalendar, curves, events, rdate, ...)
│   └── unit_tests/, manual_tests/
├── scripts/                # Helper scripts (e.g. cloud Mongo setup)
├── docs/                   # Supplementary docs (IP checklist, onboarding)
├── pyproject.toml          # Metadata, extras, scripts, uv sources/groups, dev_10x config
├── constraints.txt         # Committed third-party dependency freeze
├── ruff.toml, pytest.ini,
└── ...
```

See also:
- [`dev_10x/README.md`](dev_10x/README.md) — `xx-build` and build modes, `xx-promote`, CI gates
- Individual `*/unit_tests/` and package READMEs

## Submitting Changes

### Pull Request Process

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/your-feature-name`
3. **Make** your changes following the coding standards
4. **Add** tests for new functionality
5. **Run** the test suite: `uv run pytest`
6. **Check** code style: `uv run ruff check .`
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

- Use `manual_tests/` for debugging, demos, and live-environment checks
- Run them directly (`python path/to/script.py` or `python -m pkg.manual_tests.…`) — **not** under
  `pytest`. The py10x pytest plugin strips ambient `XX_*_VAULT_URI` so unit tests cannot inherit a
  shell vault; that makes pytest unsuitable for these scripts. A plain `pytest` run also does not
  collect `manual_tests/`.
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
