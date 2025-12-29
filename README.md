# py10x

**10x Universe Ecosystem Core**

The core package of the 10x Universe software ecosystem, designed to make 10x engineers even more productive. The structure mirrors the real world: from particles (basic data types) to atoms (object models) and molecules (fundamental programming paradigms), extending to stars and planets (subject domains).

## Overview

py10x is organized into three main packages:

- **core_10x**: Core data modeling with traits, traitables, and serialization
- **ui_10x**: Cross-platform UI components focused on traitable editing and management
- **infra_10x**: Infrastructure components including MongoDB storage integration

The `-i` packages (core_10x_i, infra_10x_i) contain the underlying C++ implementation dependencies.

**Note**: This is a pre-release version. Future releases will include enhanced tests, documentation and examples; trait validation; and automatic resource management via enterprise backbone.

## Installation

For detailed installation instructions including all prerequisites and platform-specific setup, see [INSTALLATION.md](INSTALLATION.md).

### Quick Prerequisites

- Python 3.12 (recommended), 3.10+ supported
- [UV](https://docs.astral.sh/uv/) - Python installer and package manager
- C++ compiler with C++20 support (GCC 10+, Clang 10+, MSVC 2022+, or equivalent)
  - Required for building cxx10x dependencies
- Node.js and npm (for Rio UI backend)
  - Required if using Rio UI components

### Install with UV (Recommended)

```bash
# Clone the repository
git clone https://github.com/10X-LLC/py10x.git
cd py10x

# Install everything (recommended for development)
uv sync --all-extras

# Or install specific combinations
uv sync --extra dev --extra rio  # Development + Rio UI
uv sync --extra dev --extra qt   # Development + Qt6 UI
uv sync --extra rio              # Rio UI only
uv sync --extra qt              # Qt6 UI only
```

### Install with pip

```bash
git clone https://github.com/10X-LLC/py10x.git
cd py10x
pip install -e .

# With optional dependencies
pip install -e ".[rio]"  # Rio UI backend
pip install -e ".[qt]"   # Qt6 UI backend
pip install -e ".[dev]"  # Development tools
```

## Quick Start

For a comprehensive introduction to py10x, see our [Getting Started Guide](GETTING_STARTED.md).

### Core Data Modeling with Object Identification

```python
from core_10x.traitable import Traitable, T, RC, RC_TRUE
from core_10x.exec_control import CACHE_ONLY
from datetime import date

# Endogenous traitable example
class Person(Traitable):
    # ID traits - entities with same ID share values globally
    first_name: str = T(T.ID)
    last_name: str = T(T.ID)
    
    # Regular traits (T() is required for persistence)
    dob: date = T()
    weight_lbs: float = T()
    
    # Runtime traits (not stored, computed on-demand)
    age: int = RT()  # RT() is optional for runtime traits
    full_name: str   # RT() omitted - still a runtime trait

    def age_get(self) -> int:
        """Getter method - computes age from date of birth."""
        if not self.dob:
            return 0
        today = date.today()
        return today.year - self.dob.year

    def full_name_get(self) -> str:
        """Getter method - combines first and last name."""
        return f"{self.first_name} {self.last_name}"
    
    def age_set(self, trait, value: int) -> RC:
        """Setter method - validates age and updates date of birth."""
        if value < 0:
            return RC(False, "Age cannot be negative")
        if value > 150:
            return RC(False, "Age cannot exceed 150")
        
        # Calculate date of birth from age
        today = date.today()
        birth_year = today.year - value
        self.dob = date(birth_year, today.month, today.day)
        return RC_TRUE
    
    # Note: Verification methods (e.g., age_verify) are not currently 
    # called automatically by the framework. Use setters with validation instead.

# Exogeneous traitable example
class DataCaptureEvent(Traitable):
    capture_time: datetime = T()
    raw_data: str = T()
    processed_data: str  # Runtime trait - RT() omitted (still not stored)
    
    def processed_data_get(self) -> str:
        """Runtime computation - not stored in database."""
        return self.raw_data.upper().strip()

# Use CACHE_ONLY mode - no backing database required
with CACHE_ONLY():
    # Endogenous traitables (with ID traits) share trait values globally
    person1 = Person(first_name="Alice", last_name="Smith")
    person1.dob = date(1990, 5, 15)  # Set a non-ID trait

    # Using setter method for age validation
    person1.age = 25  # Set age, updates date of birth
    print(f"Age: {person1.age}")  # 25
    print(f"Date of birth: {person1.dob}")  # Calculated from age
    
    # Test validation
    try:
        person1.age = -5  # This will fail validation
    except Exception as e:
        print(f"Validation error: {e}")

    person2 = Person(first_name="Alice", last_name="Smith")  # Same ID traits
    # person2 automatically has the same dob value as person1
    assert person2.dob == date(1990, 5, 15)  # Shared trait values
    assert person1 == person2  # Equal due to same ID traits
    # Note: person1 is person2 would be False - they're different objects

    # Exogenous traitables (no ID traits) get auto-generated UUID
    class DataCaptureEvent(Traitable):
        data: str
        timestamp: float

    # Endogenous vs Exogenous demonstration
    person = Person(first_name="Alice", last_name="Smith")  # Endogenous
    event = DataCaptureEvent(data="sensor_reading", timestamp=1234567890.0)  # Exogenous

    print(f"Person ID: {person.id()}")  # Based on ID traits (first_name, last_name)
    print(f"Event ID: {event.id()}")  # Auto-generated UUID
```

### Dependency Graph and Execution Control

```python
from core_10x.exec_control import GRAPH_ON, GRAPH_OFF, INTERACTIVE
from core_10x.traitable import Traitable, RT

class Calculator(Traitable):
    x: int = RT()
    y: int = RT()
    sum: int = RT()  # Computed via sum_get()
    product: int = RT()  # Computed via product_get()

    def sum_get(self) -> int:
        return self.x + self.y

    def product_get(self) -> int:
        return self.x * self.y

# Enable dependency graph for automatic computation
with GRAPH_ON():
    calc = Calculator(x=5, y=3)
    # sum and product computed automatically when accessed
    print(calc.sum)      # 8
    print(calc.product)  # 15
    
    calc.x = 10  # Automatically recomputes dependent traits
    print(calc.sum)      # 13
```

### Seamless UI Framework Switching

```python
# UI framework is selected automatically based on installed packages
# or environment variables - no code changes needed!

from ui_10x import Application, LineEdit, PushButton, VBoxLayout
from ui_10x.traitable_editor import TraitableEditor
from core_10x.code_samples.person import Person

def main():
    # Framework automatically chosen: Rio if available, Qt6 otherwise
    app = Application()
    
    # Create UI components (same API regardless of backend)
    line_edit = LineEdit(text="Enter text here")
    button = PushButton(text="Click me")
    
    # Layout
    layout = VBoxLayout()
    layout.add(line_edit)
    layout.add(button)
    
    # Traitable editor works with any UI framework
    person = Person(first_name="Alice", last_name="Smith")
    editor = TraitableEditor.editor(person)
    
    app.run(layout)

if __name__ == "__main__":
    main()
```

### MongoDB Integration

```python
from infra_10x import MongoStore
from core_10x import Traitable

# Connect to MongoDB
traitable_store = MongoStore.instance(
    hostname="localhost",
    dbname="myapp", 
    username="user",
    password="pass"
)

# Use traitable store context for persistence
with traitable_store:
    person = Person(first_name="Alice", last_name="Smith")
    person.dob = date(1990, 5, 15)
    person.save()  # Persists to traitable store backed by Mongo
```

## Core Features

### Object Identification System

- **Endogenous Traitables**: Traitables with ID computed from ID traits, traits shared by ID
- **Exogenous Traitables**: Traitables without ID traits get auto-generated UUIDs, traits shared by ID
- **Anonymous Traitables**: Traitables without ID - cannot be shared or persisted alone, can be embedded in other traitables
- **ID Method**: `traitable.id()` returns ID based on ID traits (endogenous) or auto-generated UUID (exogenous)
- **Global Cache**: Automatic sharing of trait values for traitables with the same ID

### Traitable Framework

The `Traitable` base class provides:

- **Trait-based attributes**: Define typed attributes with validation
- **ID Traits**: Mark traits as identifiers for global sharing
- **Regular Traits**: Used for data storage and searching
- **Runtime Traits**: Not stored, computed on-demand (RT() is optional)
- **Caching**: Built-in caching system for trait values and entity state
- **Serialization**: Automatic serialization/deserialization
- **Versioning**: Automatic revision tracking
- **Validation**: Type checking and integrity validation

### Dependency Graph System

- **Automatic Computation**: Traits computed automatically when accessed
- **Dependency Tracking**: Changes to traits trigger dependent trait updates
- **Execution Control**: Fine-grained control over computation modes
- **Performance**: Expensive computations cached and reused

### Seamless UI Framework

Cross-platform UI with automatic framework selection:

- **Auto-Detection**: Framework chosen based on installed packages
- **Environment Variables**: Override framework selection
- **Unified API**: Same code works with Rio or Qt6 backends
- **Traitable Integration**: Built-in entity editors and viewers

### Infrastructure

- **Storage Integration**: MongoDB store with revision tracking and flexible data persistence
- **Resource Management**: Manual resource management using context managers (enterprise resource management planned for future release)

## Development

### Running Tests

```bash
# Run all unit tests (with coverage by default)
pytest

# Run specific test suites
pytest core_10x/unit_tests/
pytest ui_10x/unit_tests/
pytest infra_10x/unit_tests/

# Manual tests are debugging scripts (run directly)
python core_10x/manual_tests/trivial_graph_test.py
python ui_10x/rio/manual_tests/basic_test.py
```

### Code Style

The project uses `ruff` for linting and formatting:

```bash
# Check style
ruff check .

# Fix issues
ruff check --fix .

# Format code
ruff format .
```

### Building

```bash
# Build wheel
python -m build

# Build with UV
uv build
```

## Architecture

### Core Components

- **Nucleus**: Base serialization and type system
- **Traitable**: Entity modeling with traits
- **Trait System**: Type-safe attribute definitions
- **Storage Layer**: Pluggable storage backends

### UI Architecture

- **Platform Interface**: Abstract UI component interface
- **Component Builder**: Widget construction and layout
- **Backend Implementations**: Rio and Qt6 specific implementations

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

- **Project Contact**: py10x@10xconcepts.com

## Community

Join our community on [Discord](https://discord.gg/m7AQSXfFwf) for discussion, support, and collaboration.

## Getting Help

- Check existing issues and discussions
- Ask questions in GitHub Discussions
- Join our community on [Discord](https://discord.gg/m7AQSXfFwf) for discussion, support, and collaboration
- Contact maintainers for complex issues

## Authors

- Sasha Davidovich <sasha.davidovich@10xconcepts.com>
- Ilya Pevzner <ilya.pevzner@10xconcepts.com>
- **Project Contact**: py10x@10xconcepts.com
