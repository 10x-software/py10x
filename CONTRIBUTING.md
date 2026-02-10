# Contributing to py10x-universe

Thank you for your interest in contributing to py10x-universe! This document provides guidelines for development, testing, and submitting contributions.

## Development Setup

For detailed installation instructions including all prerequisites and platform-specific setup, see [INSTALLATION.md](../INSTALLATION.md).

### Prerequisites

- Python 3.12 (recommended), 3.11+ supported
- Git
- [UV](https://docs.astral.sh/uv/) - Python installer and package manager
- C++ compiler with C++20 support (GCC 10+, Clang 10+, MSVC 2022+, or equivalent)
  - Required for building cxx10x dependencies
- MongoDB (for running tests and examples)
  - Local passwordless MongoDB instance required for running tests and examples
- Node.js and npm (for Rio UI backend)
  - Required if using Rio UI components

### Clone and Install

```bash
git clone https://github.com/10x-software/py10x.git
cd py10x

# Install everything for development (recommended)
uv sync --all-extras

# Or install specific combinations
uv sync --extra dev --extra rio  # Development + Rio UI
uv sync --extra dev --extra qt   # Development + Qt6 UI

# Or with pip
pip install -e ".[dev,rio]"  # Development + Rio UI
pip install -e ".[dev,qt]"   # Development + Qt6 UI
```

## Development Workflow

### Code Style

The project uses `ruff` for linting and formatting:

```bash
# Check for issues
ruff check .

# Auto-fix issues where possible
ruff check --fix .

# Format code
ruff format .
```

### Testing

#### Running Tests

**Note**: The `infra_10x/unit_tests/` suite requires a local MongoDB instance running on the default port (27017).

```bash
# Run all unit tests (with coverage by default)
pytest

# Run specific test suites
pytest core_10x/unit_tests/
pytest ui_10x/unit_tests/
pytest infra_10x/unit_tests/  # Requires MongoDB

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
# Example unit test
def test_traitable_creation():
    from core_10x.traitable import Traitable, T
    
    class TestEntity(Traitable):
        name: str
        value: int
    
    entity = TestEntity(name="test", value=42)
    assert entity.name == "test"
    assert entity.value == 42
```

### Building

```bash
# Build with UV (recommended)
uv build

# Or with standard tools
python -m build
```

## Project Structure

```
py10x/
├── core_10x/           # Core data modeling
│   ├── backbone/       # Backbone integration
│   ├── unit_tests/     # Core unit tests
│   └── manual_tests/   # Manual test scripts
├── ui_10x/             # UI components
│   ├── rio/           # Rio UI backend
│   ├── qt6/           # Qt6 UI backend
│   └── unit_tests/    # UI unit tests
├── infra_10x/          # Infrastructure
│   └── unit_tests/    # Infrastructure tests
└── docs/              # Documentation
```

## Submitting Changes

### Pull Request Process

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/your-feature-name`
3. **Make** your changes following the coding standards
4. **Add** tests for new functionality
5. **Run** the test suite: `pytest`
6. **Check** code style: `ruff check .`
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

When developing with the Traitable framework:

- Use `Traitable` as the base class for data models
- Define ID traits for endogenous traitables (shared globally by ID)
- Use `T()` for regular traits (required for persistence)
- Use `RT()` for runtime traits that should not be stored (RT() is optional and can be omitted)
- Implement getter methods for traits with computed values
- Use setters with validation for data integrity or to set other traits
- Leverage the dependency graph for automatic computation

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

## Release Process

### Versioning

- Follow semantic versioning (MAJOR.MINOR.PATCH)
- Update version in `pyproject.toml`
- Create release notes in CHANGELOG.md

### Release Checklist

- [ ] All tests pass
- [ ] Code style checks pass
- [ ] Documentation updated
- [ ] Version bumped
- [ ] CHANGELOG updated
- [ ] Release notes prepared

## Getting Help

- Check existing issues and discussions
- Ask questions in GitHub Discussions
- Join our community on [Discord](https://discord.gg/m7AQSXfFwf) for discussion, support, and collaboration
- Contact maintainers for complex issues

## License

Contributions are subject to the project's license terms.

## Open Source & IP

For maintainers: before publishing or major releases, see [Open Source & IP Checklist](https://github.com/10x-software/py10x/blob/main/docs/OPEN_SOURCE_IP_CHECKLIST.md) for intellectual property and license compliance.
