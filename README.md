# py10x-universe

<img src="https://10x-software.org/10x-jerboa.jpeg" alt="Jerboa Logo" width="200" height="300">

> **Early preview release – USE AT YOUR OWN RISK. NO WARRANTIES.**

**10x Universe Ecosystem Core**

The core package of the 10x Universe software ecosystem, designed to make 10x engineers even more productive. The structure mirrors the real world: from particles (basic data types) to atoms (object models) and molecules (fundamental programming paradigms), extending to stars and planets (subject domains).

## Overview

py10x-universe is organized into three main packages:

- **core_10x**: Core data modeling with traits, traitables, and serialization
- **ui_10x**: Cross-platform UI components focused on traitable editing and management
- **infra_10x**: Infrastructure components including MongoDB storage integration


## Installation

For detailed installation instructions including all prerequisites and platform-specific setup, see [INSTALLATION.md](INSTALLATION.md).

### Quick Prerequisites

- Python 3.12 (recommended), 3.11+ supported
- [UV](https://docs.astral.sh/uv/) - Python installer and package manager
- MongoDB (for running tests and examples)
  - A passwordless MongoDB instance (localhost would be the easiest) required for running some tests and examples

## Component Licensing
This package (`py10x-universe`) relies on and automatically installs `py10x-core` and `py10x-infra`, also developed by 10X CONCEPTS LLC.

While these packages are provided free of charge, they have different legal terms:
- **`py10x-universe` (This package):** Licensed under the [MIT License](https://10x-software.org/py10x_universe/LICENSE.txt).
- **`py10x-core`:** Proprietary; governed by the [Proprietary License for py10x-core](https://10x-software.org/py10x_core/LICENSE.txt).
- **`py10x-infra`:** Proprietary; governed by the [Proprietary License for py10x-infra](https://10x-software.org/py10x_infra/LICENSE.txt).

By installing `py10x-universe`, you agree to the terms of the proprietary licenses for `py10x-core` and `py10x-infra`.


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

For a comprehensive introduction to py10x-universe, see our [Getting Started Guide](GETTING_STARTED.md).

### Core Data Modeling with Object Identification

```python
from core_10x.traitable import Traitable, T, RT, RC, RC_TRUE
from core_10x.exec_control import CACHE_ONLY
from datetime import date, datetime

# Endogenous Traitable object example
class Person(Traitable):
    # ID traits - contribute to the object ID. Objects with same ID share values globally
    first_name: str = T(T.ID)
    last_name: str  = T(T.ID)
    
    # Regular traits (T() is required for persistence)
    dob: date           = T()
    weight_lbs: float   = T()
    
    # Runtime traits (not stored, computed on-demand)
    age: int            = RT()  # RT() is optional for runtime traits
    full_name: str              # RT() omitted - still a runtime trait

    def age_get(self) -> int:
        """age getter method - computes age from date of birth."""
        if not self.dob:
            return 0
        today = date.today()
        return today.year - self.dob.year

    def full_name_get(self) -> str:
        """full_name getter method - combines first and last name."""
        return f"{self.first_name} {self.last_name}"
    
    def age_set(self, trait, value: int) -> RC:
        """age setter method - validates age and updates date of birth."""
        if value < 0:
            return RC(False, "Age cannot be negative")
        if value > 150:
            return RC(False, "Age cannot exceed 150")
        
        # Calculate year of birth from age
        today = date.today()
        birth_year = today.year - value
        dob = self.dob
        self.dob = date(birth_year, dob.month, dob.day)
        return RC_TRUE

    def first_name_verify(self, t, value: str) -> RC:
        """Verifier: run on entity.verify() or entity.save(); not on set."""
        if value and value.isalpha():
            return RC_TRUE
        return RC(False, f"{t.name} may have letters only")

    def last_name_verify(self, t, value: str) -> RC:
        """Verifier: run on entity.verify() or entity.save(); not on set."""
        if value and value.isalpha():
            return RC_TRUE
        return RC(False, f"{t.name} may have letters only")
    # See [Verifiers](GETTING_STARTED.md#verifiers-validation-on-verify-and-save) for when verifiers run.

# Exogeneous Traitable object example
class DataCaptureEvent(Traitable):
    capture_time: datetime  = T()
    raw_data: str           = T()
    processed_data: str     # Runtime trait - RT() omitted (still not stored)
    
    def processed_data_get(self) -> str:
        """Runtime computation - not stored in store."""
        return self.raw_data.upper().strip()

# Use CACHE_ONLY mode - no backing store required
with CACHE_ONLY():
    # Endogenous traitables (with ID traits) share trait values globally
    person1 = Person(first_name='Alice', last_name='Smith')
    person1.dob = date(1990, 5, 15)  # Set a non-ID trait
    print( '---',person1.dob)

    # Using setter method for age validation
    person1.age = 25  # Set age, updates date of birth
    print(f'Age: {person1.age}')  # 25
    print(f'Date of birth: {person1.dob}')  # Calculated from age
    
    # Test validation
    try:
        person1.age = -5  # This will fail validation
    except Exception as e:
        print(f"Validation error: {e}")

    person1.verify().throw()  # Runs verifiers (e.g. first_name_verify); save() also calls verify()

    person2 = Person(first_name='Alice', last_name='Smith')  # Same ID traits
    # person2 automatically has the same dob value as person1
    assert person2.dob == date(2001, 5, 15)  # Shared trait values
    assert person1 == person2  # Equal due to same ID traits
    # Note: person1 is person2 would be False - they're different objects

    # Exogenous traitables (no ID traits) get auto-generated UUID
    class DataCaptureEvent(Traitable):
        data: str
        timestamp: float

    # Endogenous vs Exogenous demonstration
    person = Person(first_name='Alice', last_name='Smith')  # Endogenous
    event = DataCaptureEvent(data='sensor_reading', timestamp=1234567890.0)  # Exogenous

    print(f'Person ID: {person.id()}')  # Based on ID traits (first_name, last_name)
    print(f'Event ID: {event.id()}')    # Auto-generated UUID
```

### Dependency Graph and Execution Control

```python
from core_10x.exec_control import GRAPH_ON, GRAPH_OFF, INTERACTIVE
from core_10x.traitable import Traitable, RT

class Calculator(Traitable):
    x: int = RT()
    y: int = RT()
    sum: int        = RT()  # Computed via sum_get()
    product: int    = RT()  # Computed via product_get()

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

### Using Storage

Storable Traitable objects are kept in instances of TsStore. Currently, MongoDB is the only supportable type of TsStore.
Here's how to use a store explicitly.
```python
from infra_10x.mongodb_store import MongoStore
from core_10x.code_samples.person import Person
from datetime import date

# Connect to MongoDB
traitable_store = MongoStore.instance(hostname='localhost', dbname='myapp') 

# Use traitable store context for persistence
with traitable_store:
    person = Person(first_name='Alice', last_name='Smith')
    person.dob = date(1990, 5, 15)
    
    person.save()  # Persists to traitable store backed by Mongo
```

Alternatively, you can use TsStore with specific URI.
```python
from core_10x.ts_store import TsStore
from core_10x.code_samples.person import Person
from datetime import date

# Connect to a "passwordless" myapp store 
traitable_store = TsStore.instance_from_uri('mongodb://localhost/myapp') 

# Use traitable store context for persistence
with traitable_store:
    person = Person(first_name='Alice', last_name='Smith')
    person.dob = date(1990, 5, 15)
    
    person.save()  # Persists to traitable store myapp@localhost
```
Finally, you can specify a TsStore instance to use via an environment variable
XX_MAIN_TS_STORE_URI.
If it's defined, all storable traitable objects will be sought/saved there.

For more complex scenarios, there's a way to associate particular subclasses of Traitable to different instances of TsStore.  

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
- **Traitable**: Object modeling with traits
- **Trait System**: Type-safe attribute definitions
- **Storage Layer**: Pluggable storage backends

### UI Architecture

- **Platform Interface**: Abstract UI component interface
- **Component Builder**: Widget construction and layout
- **Backend Implementations**: Rio and Qt6 specific implementations

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. For copyright holders, proprietary components, and third-party attributions, see [NOTICE](NOTICE).

## Legal & Security
- This project is developed and maintained by **10X CONCEPTS LLC**. **USE AT YOUR OWN RISK. NO WARRANTIES.**
- Dependencies have been audited for known vulnerabilities and license compatibility (see checklist in release notes).
- For security issues or vulnerabilities, please report privately to <security@10x-software.org> (do **not** open public issues).
- See [SECURITY.md](SECURITY.md) for full security policy, reporting guidelines, and known issues.

## Contact

- **Project Contact**: py10x@10x-software.org

## Getting Help

- Check existing issues and discussions
- Ask questions in GitHub Discussions
- Join our community on [Discord](https://discord.gg/m7AQSXfFwf) for discussion, support, and collaboration
- Contact maintainers for complex issues

