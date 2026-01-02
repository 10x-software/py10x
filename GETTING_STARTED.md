from core_10x.exec_control import CACHE_ONLY

# Getting Started with py10x

Welcome to py10x - the core of the 10x Universe Ecosystem! 
This comprehensive guide will walk you through the fundamental concepts, installation, and usage of py10x packages.

## Table of Contents

1. [What is py10x?](#whats-in-py10x)
2. [Installation](#installation)
3. [Core Concepts](#core-concepts)
4. [Your First Traitable](#your-first-traitable)
5. [Object Identification System](#object-identification-system)
6. [Storage and Persistence](#storage-and-persistence)
7. [Dependency Graph and Execution Control](#dependency-graph-and-execution-control)
8. [Traitable Store](#traitable-store)
9. [UI Framework Integration](#ui-framework-integration)
10. [Advanced Features](#advanced-features)
11. [Next Steps](#next-steps)

## What's in py10x?

- **Traitable Framework**: Core data modeling with traits, traitables, and serialization
- **Object Identification**: Endogenous, exogenous, and anonymous traitables with global sharing
- **Dependency Graph**: Automatic computation and dependency tracking
- **Seamless UI Integration**: Rio and Qt6 backends with unified API
- **Storage Integration**: MongoDB and in-memory caching
- **Built-in Caching**: Automatic trait value and traitable state management

## Installation

### Prerequisites

- Python 3.12 (recommended), 3.10+ supported
- MongoDB (for running storage examples)
  - Local passwordless MongoDB instance required for running storage examples

### Install

```bash
# Install py10x with UI backend
pip install py10x[rio]    # For Rio UI backend
# or
pip install py10x[qt]     # For Qt6 backend
```

**For Development**: See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup instructions.

## Core Concepts

### Traitables

Traitables are the fundamental data models in py10x. They are Python classes that inherit from `Traitable` and define typed attributes called "traits".

### Traits

Traits are typed attributes that can be:
- **Regular traits**: Stored and searchable (use `T()`)
- **Runtime traits**: Not stored, computed on-demand (use `RT()` or omit)
- **ID traits**: Define traitable identity for global sharing (use `T(T.ID)`)

**Note**: Any trait (regular or runtime) can be computed on-demand if there is a getter method defined.

### Object Identification

All traitables have an ID and all traitables with the same ID share trait values:

- **Endogenous Traitables**: ID generated from ID traits, share values globally by ID
- **Exogenous Traitables**: ID is auto-generated UUID, share values globally by ID
- **Anonymous Traitables**: Each instance gets its own ID (e.g., instance address), cannot be persisted alone
- **Runtime Traitables**: Can be any of the above types, but never persisted (all traits are runtime)

## How Traitables Are Created

Understanding traitable creation is key to using the framework effectively:

### Creation Process

1. **ID Construction**: ID traits are evaluated to create the traitable's identity
2. **Global Lookup**: Framework searches for existing traitable with same ID in:
   - Memory cache (global cache)
   - Storage backend (if available)
3. **Instance Handling**:
   - **Always creates new instance** - construction never returns existing instance
   - **Shares trait values** with any existing instance that has the same ID
   - If no existing instance found: Creates new instance with default trait values
   - If existing instance found: Creates new instance but shares trait values from existing instance

### Why Storage Context is Required

```python
from core_10x.exec_control import CACHE_ONLY
from core_10x.traitable import Traitable, T, RT
from datetime import date

# This requires storage context because Person has regular (stored) traits
class Person(Traitable):
    first_name: str = T(T.ID)
    last_name: str = T(T.ID)
    dob: date = T() 

# Storage context required for non-runtime traitables
with CACHE_ONLY():  # or MongoStore.instance()
    person = Person(first_name="Alice", last_name="Smith")
    person.dob = date(1990, 5, 15)
```

### Runtime Traitables Exception

```python
from core_10x.traitable import Traitable

class Calculator(Traitable):
    x: int  # Runtime trait
    y: int  # Runtime trait
    sum: int  # Runtime trait

# No storage context needed for runtime traitables
calc = Calculator(x=5, y=3)
```

## Getters, Setters, and Validation

py10x provides powerful mechanisms for computed traits, validation, and data transformation:

### Getters (Computed Traits)

Any trait can be computed on-demand by defining a getter method:

```python
from core_10x.exec_control import CACHE_ONLY
from core_10x.traitable import Traitable, T, RT
from datetime import date

class Person(Traitable):
    first_name: str = T(T.ID)  # ID trait
    last_name: str = T(T.ID)   # ID trait
    dob: date = T()
    
    # Computed traits using getters
    full_name: str = RT()  # Runtime trait
    age: int = T()         # Regular trait that can be computed
    
    def full_name_get(self) -> str:
        """Getter method - computes full name on-demand."""
        return f"{self.first_name} {self.last_name}"
    
    def age_get(self) -> int:
        """Getter method - computes age from date of birth."""
        if not self.dob:
            return 0
        today = date.today()
        return today.year - self.dob.year

# Usage
with CACHE_ONLY():
    person = Person(first_name="Alice", last_name="Smith", dob=date(1990, 5, 15), _force=True)
    assert person.full_name == "Alice Smith"  # Computed
    assert person.age == 36  # Computed from dob
```

### Setters (Validation and Transformation)

Setters provide validation and data transformation. They are automatically called on assignment:

```python
from core_10x.traitable import Traitable, T, RC, RC_TRUE

class Person(Traitable):
    email: str
    age: int
    
    def email_set(self, trait, value: str) -> RC:
        """Setter method - validates email format."""
        if '@' not in value or '.' not in value.split('@')[1]:
            return RC(False, f'Invalid email format: "{value}"')
        
        # Use raw_set_value to bypass the setter
        return self.raw_set_value(trait, value)
    
    def age_set(self, trait, value: int) -> RC:
        """Setter method - validates age range."""
        if value < 0:
            return RC(False, "Age cannot be negative")
        if value > 150:
            return RC(False, "Age cannot exceed 150")
        
        return self.raw_set_value(trait, value)

# Usage with automatic validation
person = Person()

# Setters are called automatically on assignment
try:
    person.email = 'invalid-email'  # Throws exception with "Invalid email format"
except RuntimeError as e:
    assert "Invalid email format" in str(e)

person.email = 'alice@example.com'  # Valid email - succeeds
person.age = 25  # Valid age - succeeds

# Programmatic setting with accumulated RC
result = person.set_values(age=30, email='bob@example.com')
if not result:
    assert False, f"Set failed: {result.errors()}"
```

### Setters Can Propagate Values to Other Traits

```python
from core_10x.traitable import Traitable, T, RC, RC_TRUE

class Person(Traitable):
    first_name: str
    last_name: str
    full_name: str
    
    def full_name_set(self, trait, value: str) -> RC:
        """Setter that propagates to other traits when full name is set."""
        # Don't set full_name - let the getter compute it
        # Instead, propagate to other traits by splitting the full name
        name_parts = value.strip().split(' ', 1)  # Split on first space only
        if len(name_parts) == 2:
            self.first_name = name_parts[0]
            self.last_name = name_parts[1]
        elif len(name_parts) == 1:
            self.first_name = name_parts[0]
            self.last_name = ""
        
        return RC_TRUE
    
    def full_name_get(self) -> str:
        """Getter that computes full name from first and last names."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        else:
            return ""

# Usage - setting full name automatically splits into first and last
person = Person()
person.full_name = "Alice Smith"  # Automatically sets first_name="Alice" and last_name="Smith"

assert person.first_name == "Alice"  # Propagated
assert person.last_name == "Smith"   # Propagated
assert person.full_name == "Alice Smith"  # Computed from first_name + last_name

# Setting individual names and computing full name
person.first_name = "Bob"
person.last_name = "Johnson"
assert person.full_name == "Bob Johnson"  # Computed by getter

# Setting full name with single name
person.full_name = "Madonna"  # Sets first_name="Madonna", last_name=""
assert person.first_name == "Madonna"
assert person.last_name == ""
assert person.full_name == "Madonna"  # Computed by getter
```

**Key Difference from Converters:**
- **Converters**: Transform the input value for the same trait
- **Setters**: Can set multiple traits in response to one assignment
- **Use Case**: Business logic that requires updating related data when one field changes


### Convert Methods

Converters are automatically called when there's a **type mismatch** between the assigned value and the trait type:

```python
from core_10x.traitable import Traitable, T, RC, RC_TRUE
from core_10x.exec_control import CONVERT_VALUES_ON, CONVERT_VALUES_OFF, DEBUG_ON

class Person(Traitable):
    name: bytes  # Expects bytes (runtime trait)
    status: str  # Expects string (runtime trait)
    
    def name_from_str(self, trait, value: str) -> bytes:
        """Convert from string - title case the name."""
        return value.title().encode()
    
    def name_from_any_xstr(self, trait, value) -> bytes:
        """Convert from non-string - convert to string and title case."""
        return str(value).title().encode()
    
    def status_from_any_xstr(self, trait, value) -> str:
        """Convert any value to lowercase string."""
        return str(value).lower()

# With CONVERT_VALUES_ON - converters called for type mismatches
with CONVERT_VALUES_ON():
    person = Person()
    person.name = "alice smith"  # str -> bytes (mismatch) - calls name_from_str
    person.status = True         # bool -> str (mismatch) - calls status_from_any_xstr
    
    assert person.name == b"Alice Smith"  # Converted to bytes
    assert person.status == "true"        # Converted to string

# With CONVERT_VALUES_OFF - no automatic conversion
with CONVERT_VALUES_OFF():
    person = Person()
    person.name = "alice smith"  # No conversion - stores as string
    person.status = "active"     # No conversion - stores as string
    
    assert person.name == "alice smith"  # Stored as-is
    assert person.status == "active"     # Stored as-is
```

### Convert vs Getter/Setter

- **`_from_str` methods**: Automatic conversion when setting string values
- **`_from_any_xstr` methods**: Automatic conversion when setting non-string values
- **`_get` methods**: Computation when accessing values  
- **`_set` methods**: Validation and transformation when setting values
- **Setters can propagate to other traits**: Unlike converters, setters can set multiple traits in response to one assignment


## Your First Traitable

Let's start with a simple runtime traitable that doesn't require storage context:

```python
from core_10x.traitable import Traitable

class Calculator(Traitable):
    # Runtime traits - computed on-demand, not stored
    x: int
    y: int
    sum: int      # Computed via sum_get()
    product: int  # Computed via product_get()

    def sum_get(self) -> int:
        """Getter method - computes sum of x and y."""
        return self.x + self.y

    def product_get(self) -> int:
        """Getter method - computes product of x and y."""
        return self.x * self.y

# Runtime traitables work without storage context
calc = Calculator(x=5, y=3)
assert calc.sum == 8        # 8
assert calc.product == 15   # 15

# Update values and see automatic recomputation
calc.x = 10
assert calc.sum == 13    # 13
```

## Object Identification System

All traitables have an ID and share trait values globally by ID. Let's explore the different types:

### Endogenous Traitables (ID from ID Traits)

```python
from core_10x.traitable import Traitable, RT, T
from core_10x.exec_control import CACHE_ONLY

class Person(Traitable):
    # ID traits - define identity for global sharing
    first_name: str = RT(T.ID)
    last_name: str = RT(T.ID)

    # Runtime traits, computed on-demand
    full_name: str
    initials: str

    def full_name_get(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def initials_get(self) -> str:
        return f"{self.first_name[0]}{self.last_name[0]}"

# Endogenous traitables: ID generated from ID traits
person1 = Person(first_name="Alice", last_name="Smith")
person2 = Person(first_name="Alice", last_name="Smith")  # Same ID traits = same ID

# Both instances share the same computed values (same ID)
assert person1.full_name == person2.full_name  # "Alice Smith"
assert person1.initials == person2.initials    # "AS"
assert person1 == person2  # Equal due to same ID
assert person1.id() == person2.id()  # Same ID
# Note: person1 is person2 would be False - they're different objects
```

#### Constructor Parameter: `_force=True`

When creating endogenous traitable instances with **non-ID traits** (regular or runtime traits), you must use the `_force=True` parameter to indicate that an existing instance should be updated if found:

```python
from core_10x.traitable import Traitable, T
from core_10x.exec_control import CACHE_ONLY
from datetime import date

class Person(Traitable):
    # ID traits
    first_name: str = T(T.ID)
    last_name: str = T(T.ID)

    # Non-ID traits (require _force=True when provided in constructor)
    dob: date = T()
    age: int

    def age_get(self) -> int:
        if not self.dob:
            return 0
        today = date.today()
        return today.year - self.dob.year

# Use _force=True when providing non-ID traits in constructor
with CACHE_ONLY():
    person = Person(first_name="Alice", last_name="Smith", dob=date(1990, 5, 15), _force=True)
    assert person.age > 30  # Computed from dob (age depends on current year)
```

Without `_force=True`, providing non-ID traits in the constructor would raise an error, as the framework assumes ID-only construction for endogenous traitables by default.

### Exogenous Traitables (Auto-generated UUID)

```python
from core_10x.traitable import Traitable, T
from core_10x.exec_control import CACHE_ONLY
from datetime import datetime

class DataCaptureEvent(Traitable):
    # No ID traits - gets auto-generated UUID
    capture_time: datetime = T()
    raw_data: str = T()
    processed_data: str  # Runtime trait

    def processed_data_get(self) -> str:
        """Runtime computation - not stored in database."""
        return self.raw_data.upper().strip()

# Exogenous traitables: ID is auto-generated UUID
with CACHE_ONLY():
    event1 = DataCaptureEvent(capture_time=datetime.now(), raw_data="sensor_reading")
    event2 = DataCaptureEvent(capture_time=datetime.now(), raw_data="sensor_reading")

    assert event1.id() != event2.id()  # Different UUIDs
    assert event1 != event2  # Different instances, different IDs
```

### Anonymous Traitables (Instance-specific ID)

```python
from core_10x.traitable import Traitable, T, AnonymousTraitable
from core_10x.exec_control import CACHE_ONLY


class AnonymousData(AnonymousTraitable):
    # No ID traits - each instance gets its own ID (e.g., instance address)
    value: str = T()
    timestamp: float = T()


class DataRecord(Traitable):
    name: str = T(T.ID)
    data: AnonymousData = T(T.EMBEDDED)  # Embedded anonymous traitable


# Anonymous traitables: each instance gets its own ID
with CACHE_ONLY():
    record = DataRecord(name="sensor_001", data=AnonymousData(value="temp: 72.5", timestamp=1234567890.0), _force=True)
    assert record.data.id() is not None  # Instance-specific ID
```

### Runtime Traitables (Only runtime traits, Never Persisted)

```python
from core_10x.traitable import Traitable

class Calculator(Traitable):
    # Only runtime traits - can be any identification type
    x: int
    y: int
    sum: int
    product: int

    def sum_get(self) -> int:
        return self.x + self.y

    def product_get(self) -> int:
        return self.x * self.y

# Runtime traitables: never persisted, all traits are runtime
calc = Calculator(x=5, y=3)
assert calc.id() is not None  # Has ID but never persisted
```

## Storage and Regular Traits

Now let's introduce storage and regular (stored) traits:

### Regular Traits with Storage Context

```python
from core_10x.traitable import Traitable, T, RC, RC_TRUE
from core_10x.exec_control import CACHE_ONLY
from datetime import date

class Person(Traitable):
    # ID traits - define identity for global sharing
    first_name: str = T(T.ID)
    last_name: str = T(T.ID)
    
    # Regular traits - stored and searchable
    dob: date = T()
    weight_lbs: float = T()
    
    # Runtime traits - computed on-demand, not stored
    age: int
    full_name: str

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
        dob = self.dob
        self.dob = date(birth_year, dob.month, dob.day)
        return RC_TRUE

# Regular traits require storage context
with CACHE_ONLY():  # No traitable store, in-memory caching only
    person = Person(first_name="Alice", last_name="Smith")
    person.dob = date(1990, 5, 15)
    person.weight_lbs = 130.0
    
    # Access computed traits
    assert person.age == 36         # Computed from dob
    assert person.full_name == "Alice Smith" # Computed from first_name + last_name
    
    # Use setter with validation
    person.age = 25  # Updates dob automatically
    assert person.dob == date(2001, 5, 15)  # Updated DOB
```

### MongoDB Storage Integration

```python
from datetime import date
from infra_10x.mongodb_store import MongoStore
from core_10x.code_samples.person import Person

# Connect to MongoDB
traitable_store = MongoStore.instance(
    hostname="localhost",
    dbname="myapp", 
)

# Use traitable store context for persistence
with traitable_store:
    person = Person(first_name="Alice", last_name="Smith")
    person.dob = date(1990, 5, 15)
    person.save()  # Persists to traitable store backed by Mongo
```

### Traitable Store Union (TsUnion)

TsUnion allows you to combine multiple storage backends for unified access:

```python
from datetime import date    

from core_10x.code_samples.person import Person
from core_10x.trait_filter import f
from core_10x.traitable import Traitable, T
from core_10x.ts_union import TsUnion
from infra_10x.mongodb_store import MongoStore

# Create multiple stores
dev_store = MongoStore.instance(hostname="localhost", dbname="my_dev_data")
prod_store = MongoStore.instance(hostname="localhost", dbname="my_prod_data")

# Create a union of stores
ts_union = TsUnion(dev_store, prod_store)

# Use the union for unified access
with ts_union:
    
    # Usage with TsUnion
    person = Person(first_name="Alice", last_name="Smith")
    person.dob = date(1990, 5, 15)
    person.save()  # Persists to all stores in the union

    # Search across all stores
    assert Person.load_many(f(first_name="Alice"))[0].first_name=='Alice'

with dev_store:
    assert Person.load_many(f(first_name="Alice"))[0].first_name=='Alice'

with prod_store:
    assert not Person.load_many(f(first_name="Alice"))

```

### How TsUnion Works

TsUnion provides a unified interface to multiple storage backends with a hierarchical approach:

1. **Write Operations**: Saves to the **first store** in the union (head store)
2. **Read Operations**: 
   - **Load**: Searches stores in order, returns first match found
   - **Find/Search**: Merges results from ALL stores, sorted by order
3. **Delete Operations**: Deletes from head store, but only succeeds if object doesn't exist in other stores
4. **Collection Operations**: Combines collection names from all stores
5. **Aggregation**: Min/max operations work across all stores

**Key Behavior**:
- The **first store** is the primary (head) - all writes go there
- **Other stores** are read-only for the union (tail stores)
- **Search results** are merged and sorted from all stores
- **Load operations** return the first match found in any store

This is particularly useful for:
- **Read scaling** across multiple data sources
- **Data migration** with fallback to multiple stores
- **Unified access** to distributed data
- **Backup integration** where primary store is backed by read-only stores

## Traitable Type Traits

Traitables can reference other traitables through type traits:

### Reference Traits (Stored by Reference)

```python
from core_10x.exec_control import CACHE_ONLY
from core_10x.traitable import Traitable, T

class Company(Traitable):
    name: str = T(T.ID)
    founded_year: int = T()

class Employee(Traitable):
    first_name: str = T(T.ID)
    last_name: str = T(T.ID)
    company: Company = T()  # Reference to another traitable

# Create company and employee
with CACHE_ONLY():
    company = Company(name="Acme Corp", founded_year=2020, _force=True)
    employee = Employee(first_name="Alice", last_name="Smith", company=company, _force=True)
    
    # The company is stored by reference
    assert employee.serialize_object()['company'] == {'_id': 'Acme Corp'}
```

### Embedded Traits (Stored Embedded)

```python
from core_10x.exec_control import CACHE_ONLY
from core_10x.traitable import Traitable, T, AnonymousTraitable


class Address(AnonymousTraitable):
    street: str = T()
    city: str = T()
    zip_code: str = T()


class Person(Traitable):
    first_name: str = T(T.ID)
    last_name: str = T(T.ID)
    address: Address = T(T.EMBEDDED)  # Embedded traitable


# Create person with embedded address
with CACHE_ONLY():
    person = Person(
        first_name="Alice",
        last_name="Smith",
        address=Address(street="123 Main St", city="Anytown", zip_code="12345"),
        _force=True
    )
    
    # The address is stored embedded within the person
    assert person.serialize_object()['address'] == {'street': '123 Main St', 'city': 'Anytown', 'zip_code': '12345'}
```

## Execution Modes and Control

py10x provides fine-grained control over computation and execution through execution modes. Each mode has specific overhead and benefits that should be considered based on your use case.

### Graph Execution Modes

#### GRAPH_ON - Dependency Tracking and Caching

**What it does**: Enables caching of automatic computations and tracks dependencies between traits.
- **Overhead**: Maintains dependency graph in memory, tracks trait relationships, triggers recomputation when dependencies change
- **Benefits**: Cached trait computation when accessed, dependency tracking ensures consistency, efficient for complex trait relationships
- **When to use**: When recomputation is more expensive than maintaining the dependency graph, or when you have complex trait relationships

**GRAPH_OFF**: The opposite of GRAPH_ON - disables dependency tracking and caching for fresh computation on every access.

```python
from core_10x.traitable import Traitable
from core_10x.exec_control import GRAPH_ON, GRAPH_OFF

class Calculator(Traitable):
    x: int
    y: int
    sum: int
    
    def sum_get(self) -> int:
        return self.x + self.y

# With dependency tracking and caching
with GRAPH_ON():
    calc = Calculator(x=5, y=3)
    assert calc.sum == 8  # Computed and cached
    assert calc.sum == 8  # From cache
    calc.x = 6
    assert calc.sum == 9  # Getter called again due to dependency change

# Without dependency tracking, fresh computation every time
with GRAPH_OFF():
    calc = Calculator(x=5, y=3)
    assert calc.sum == 8  # Getter called
    assert calc.sum == 8  # Getter called again (no caching)
    calc.x = 6
    assert calc.sum == 9  # Getter called again (no caching)
```

#### INTERACTIVE - Required for UI Usage

**What it does**: Enables dependency tracking with caching and allows UI elements to attach to the dependency graph for automatic updates.
- **Overhead**: Maintains dependency graph in memory, tracks UI element connections, triggers UI updates when dependencies change
- **Benefits**: Cached trait computation with automatic UI updates when data changes, seamless integration with user interface elements, real-time synchronization between data and UI
- **When to use**: **Required for all UI usage** - enables UI elements to automatically update when underlying data changes

```python
from core_10x.traitable import Traitable
from core_10x.exec_control import INTERACTIVE

class Calculator(Traitable):
    x: int
    y: int
    sum: int
    
    def sum_get(self) -> int:
        return self.x + self.y

with INTERACTIVE():
    calc = Calculator(x=5, y=3)
    calc.bui_class().create_ui_node(calc, calc.T.sum, lambda: print('callback called'))
    assert calc.sum == 8  # Computed and cached
    calc.x = 10  # UI elements automatically update via callbacks
    assert calc.sum == 13  # Updated automatically
```

### Conversion Modes

#### CONVERT_VALUES_ON - Automatic Type Conversion

**What it does**: Enables automatic conversion between data types when setting trait values.
- **Overhead**: Type checking and conversion on each assignment, potential performance impact with frequent assignments, memory overhead for conversion logic
- **Benefits**: Flexible data input from various sources, automatic handling of string-to-type conversions, reduces data preparation overhead
- **When to use**: When your data sources provide different types (e.g., CSV files with string numbers, JSON with mixed types, user input), or when you need flexible data ingestion

**CONVERT_VALUES_OFF**: The opposite of CONVERT_VALUES_ON - disables automatic conversion, requiring exact type matches.

```python
from core_10x.traitable import Traitable
from core_10x.exec_control import CONVERT_VALUES_ON, CONVERT_VALUES_OFF
from core_10x.trait_method_error import TraitMethodError

class Calculator(Traitable):
    x: int
    y: int
    sum: int
    
    def sum_get(self) -> int:
        return self.x + self.y

# With automatic type conversion
with CONVERT_VALUES_ON():
    calc = Calculator()
    calc.x = "5"        # String converted to int
    calc.y = "3"        # String converted to int
    assert calc.sum == 8
    assert calc.x == 5
    assert calc.y == 3

# With strict type checking
with CONVERT_VALUES_OFF():
    calc = Calculator()
    calc.x = "5"       # No conversion occur
    calc.y = "3"       # No conversion occur
    assert calc.sum == "53" # sString concatenation in place of addition!
    assert calc.x == "5"
    assert calc.y == "3"
    

```

### Debug Modes

#### DEBUG_ON - Runtime Type Checking

**What it does**: Enables comprehensive runtime type checking, validation, and detailed error reporting.
- **Overhead**: Runtime type checking on every operation, detailed error tracking and reporting, performance impact on trait access and assignment
- **Benefits**: Comprehensive error detection, detailed error messages with context, runtime validation of trait constraints, development and debugging support
- **When to use**: During development, testing, or when debugging complex trait relationships and data validation issues

**DEBUG_OFF**: The opposite of DEBUG_ON - disables debug features for maximum performance.

```python
from core_10x.exec_control import DEBUG_ON, DEBUG_OFF
from core_10x.traitable import Traitable
from core_10x.trait_method_error import TraitMethodError

class Calculator(Traitable):
    x: int
    y: int
    sum: int
    
    def sum_get(self) -> int:
        return self.x + self.y

# With runtime type checks for debugging
calc = Calculator()

with DEBUG_ON():
    try:
        calc.x = "five"  # Detailed type error
    except TypeError as e:
        print('===',str(e))
        assert str(e) == "Calculator.x (<class 'int'>) - invalid value 'five'"  # Comprehensive error information

    
# Production mode
with DEBUG_OFF():
    calc.x = "five" # No checking
    calc.y = 3
    try:
        calc.sum # Error in the getter due to type mismatch
    except TraitMethodError as e:
        assert (
            str(e)
            == f"""Failed in <class 'Calculator'>.sum.sum_get
    object = {calc.id().value};
    value = ()
    args = can only concatenate str (not "int") to str"""
        )
```


### Storage Context Modes

#### CACHE_ONLY - In-Memory Operations

**What it does**: Provides in-memory caching without persistent storage.

**Use case**: Testing, temporary computations, or when persistence is not needed.

```python
from core_10x.exec_control import CACHE_ONLY
from core_10x.traitable import Traitable, T

class Person(Traitable):
    first_name: str = T(T.ID)
    last_name: str = T(T.ID)
    full_name: str
    
    def full_name_get(self) -> str:
        return f"{self.first_name} {self.last_name}"

with CACHE_ONLY():
    person = Person(first_name="Alice", last_name="Smith")
    # Operations work in memory only
    assert person.full_name == "Alice Smith"  # Computed and cached in memory
```

## Traitable Store

Traitable Store is essential for persistence and data management. 
The storage context is used for finding and loading traitables.

### Storage Context and Traitable Creation

Storage context is required for traitable creation because the constructor needs to:
1. Construct the ID from ID traits
2. Look for existing instances in memory and storage
3. Set additional trait values if no shared instance is found

```python
from infra_10x.mongodb_store import MongoStore
from core_10x.traitable import Traitable, T
from datetime import date

class Person(Traitable):
    first_name: str = T(T.ID)
    last_name: str = T(T.ID)
    dob: date = T()

# Storage context is required for traitable creation
with MongoStore.instance(hostname="localhost", dbname="myapp"):
    # Constructor uses storage to find existing instances
    person = Person(first_name="Alice", last_name="Smith")
    person.dob = date(1990, 5, 15)
    person.save()  # Persists to MongoDB
```

### Traitable Finding Methods

Traitable store provides several methods for finding and loading traitables:

#### Load by ID

```python
from core_10x.traitable_id import ID
from infra_10x.mongodb_store import MongoStore
from core_10x.traitable import Traitable, T

class Person(Traitable):
    first_name: str = T(T.ID)
    last_name: str = T(T.ID)

# Load a specific traitable by ID (requires storage context)
with MongoStore.instance(hostname="localhost", dbname="myapp"):
    person_id = ID("Alice|Smith")  # ID for endogenous traitable
    person = Person.load(person_id)
    if person:
        assert person.first_name == "Alice"
        assert person.last_name == "Smith"
    else:
        assert False, "Person not found"
```

#### Load Multiple IDs

```python
from core_10x.traitable_id import ID
from infra_10x.mongodb_store import MongoStore
from core_10x.traitable import Traitable, T
from core_10x.trait_filter import f,IN
from datetime import date

class Person(Traitable):
    first_name: str = T(T.ID)
    last_name: str = T(T.ID)
    dob: date = T()

# First, create and save multiple people (requires storage context)
with MongoStore.instance(hostname="localhost", dbname="myapp"):
    person1 = Person(first_name="Alice", last_name="Smith")
    person1.dob = date(1990, 5, 15)
    person1.save()
    
    person2 = Person(first_name="Bob", last_name="Johnson")
    person2.dob = date(1985, 3, 20)
    person2.save()

    # Load multiple traitables by their IDs
    person_ids = ["Alice|Smith", "Bob|Johnson"]
    people = Person.load_many(f(_id=IN(person_ids)))
    assert len(people) == 2
    assert people[0].first_name == "Alice"
    assert people[0].last_name == "Smith"
    assert people[1].first_name == "Bob"
    assert people[1].last_name == "Johnson"
```

#### Filters

```python
from core_10x.trait_filter import f, GT, AND
from infra_10x.mongodb_store import MongoStore
from core_10x.traitable import Traitable, T
from core_10x.trait_filter import f, GT, AND
from datetime import date

class Person(Traitable):
    first_name: str = T(T.ID)
    last_name: str = T(T.ID)
    dob: date = T()

# Find traitables using filters (requires storage context)
with MongoStore.instance(hostname="localhost", dbname="myapp"):
    # Find all people with last name "Smith"
    smith_people = Person.load_many(f(last_name="Smith"))
    
    # Find people born after 1990
    young_people = Person.load_many(f(dob=GT(date(1990, 1, 1))))
    
    # Complex filter: Smiths born after 1990
    young_smiths = Person.load_many(
        AND(f(last_name="Smith"), f(dob=GT(date(1990, 1, 1))))
    )
    
    # Verify the filter results
    assert len(young_smiths) > 0
    for person in young_smiths:
        assert person.last_name == "Smith"
        assert person.dob > date(1990, 1, 1)
```

#### Find Existing Instance

The `existing_instance` method is similar to the constructor but returns `None` if no existing instance is found:

```python
from infra_10x.mongodb_store import MongoStore
from core_10x.traitable import Traitable, T

class Person(Traitable):
    first_name: str = T(T.ID)
    last_name: str = T(T.ID)

# Try to find existing person, return None if not found
with MongoStore.instance(hostname="localhost", dbname="myapp"):
    person = Person.existing_instance(first_name="Alice", last_name="Smith")
    if person:
        assert person.first_name == "Alice"
        assert person.last_name == "Smith"
    else:
        assert False, "Person not found"
```

### Storage Context Modes

#### CACHE_ONLY - In-Memory Operations

```python
from core_10x.exec_control import CACHE_ONLY
from core_10x.traitable import Traitable, T
from datetime import date

class Person(Traitable):
    first_name: str = T(T.ID)
    last_name: str = T(T.ID)
    dob: date = T()

# Use in-memory caching without backing database
with CACHE_ONLY():
    person = Person(first_name="Alice", last_name="Smith")
    person.dob = date(1990, 5, 15)
    # No persistence, but full traitable functionality available
```

#### MongoDB Integration

```python
from core_10x.traitable import Traitable, T
from datetime import date
from infra_10x.mongodb_store import MongoStore

class Person(Traitable):
    first_name: str = T(T.ID)
    last_name: str = T(T.ID)
    dob: date = T()
    
# Connect to MongoDB
with MongoStore.instance(hostname="localhost", dbname="myapp"):
    person = Person(first_name="Alice", last_name="Smith")
    person.dob = date(1990, 5, 15)
    person.save()  # Persists to MongoDB
```

## UI Framework Integration

py10x provides seamless UI framework switching between Rio and Qt6 with specialized components for traitable editing:

### Traitable Editor

Edit individual traitables with automatic form generation:

```python
from core_10x.code_samples.person import Person
from ui_10x.traitable_editor import TraitableEditor, TraitableView
from infra_10x.mongodb_store import MongoStore

# Create a person traitable
with MongoStore.instance(hostname='localhost', dbname='test'):
    person = Person(first_name='Sasha', last_name='Davidovich')
    
    # Create editor with custom view
    view = TraitableView.modify(Person)
    editor = TraitableEditor.editor(person, view=view)
    
    # Show dialog for editing
    result = editor.dialog(save=True).exec()
```

### Collection Editor

Edit collections of traitables with full CRUD operations:

```python
from core_10x.code_samples.person import Person
from ui_10x.collection_editor import Collection, CollectionEditor
from ui_10x.utils import UxDialog, ux
from infra_10x.mongodb_store import MongoStore

# Initialize UI framework
ux.init()

with MongoStore.instance(hostname='localhost', dbname='test'):
    # Create collection of Person traitables
    collection = Collection(cls=Person)
    
    # Create collection editor
    editor = CollectionEditor(coll=collection)
    widget = editor.main_widget()
    
    # Show in dialog
    dialog = UxDialog(widget)
    dialog.exec()
```

### Framework Selection

The UI framework is automatically selected based on available packages:

```python
# Rio backend (if rio-ui is installed)
import os
os.environ['UI_PLATFORM'] = 'Rio'

# Qt6 backend (if PyQt6 is installed)  
os.environ['UI_PLATFORM'] = 'Qt'

# Or let the framework auto-detect
# (default behavior)
```


## Advanced Features

### Named Constants

py10x provides powerful named constant systems for type-safe enumerations and flags:

#### Basic Named Constants

```python
from core_10x.named_constant import NamedConstant

class Status(NamedConstant,default_labels=True,lowercase_values=True):
    ACTIVE = ()
    INACTIVE = 'inact'
    PENDING = ()
# Usage
status = Status.ACTIVE
assert status.label == "Active"
assert status.value == 'active'
assert Status.INACTIVE.value == 'inact'
```

#### Enums

```python
from core_10x.named_constant import Enum

class Priority(Enum,seed=1):
    LOW = ()
    MEDIUM = () 
    HIGH = ()
    CRITICAL = 'CRIT'

# Auto-generated integer values
assert Priority.LOW.value == 1
assert Priority.MEDIUM.value == 2
assert Priority.HIGH.value == 3
assert Priority.CRITICAL.value == 4
assert Priority.CRITICAL.label == 'CRIT'
```

#### Enum Bits (Flags)

```python
from core_10x.named_constant import EnumBits

class Permissions(EnumBits):
    READ = ()
    WRITE = ()
    EXECUTE = ()

# Bitwise operations
user_perms = Permissions.READ | Permissions.WRITE
assert user_perms.value == 3  # 3 (binary: 11)

# Check permissions
assert user_perms & Permissions.READ  # User has read access
```

### Traitable Filters

Traitable filters provide powerful querying capabilities:

```python
from core_10x.trait_filter import f, EQ, GT, LT, AND, OR
from core_10x.traitable import Traitable, T
from core_10x.named_constant import NamedConstant
from infra_10x.mongodb_store import MongoStore


class Status(NamedConstant):
    ACTIVE = ()
    INACTIVE = ()

class Person(Traitable):
    status: Status = T(Status.ACTIVE)
    age: int = T()
    salary: float = T()

with MongoStore.instance(
    hostname="localhost",
    dbname="myapp", 
):
    Person.delete_collection() # delete all existing entries from store, if any
    
    # create a few examples
    Person(age=15,salary=1000).save()
    Person(age=20,salary=10000).save()
    Person(age=30,salary=100000).save()
    Person(age=40,salary=1000000).save()
    Person(age=50,status=Status.INACTIVE).save()
    
    # Simple filters
    active_users = Person.load_many(f(status=EQ(Status.ACTIVE)))
    assert len(active_users) == 4
    adults = Person.load_many(f(age=GT(18)))
    assert len(adults) == 4
    
    # Complex filters
    filtered = Person.load_many(
        f(
            OR(
                f(salary = LT(50000)),
                f(salary = GT(100000))
            ),
            status=EQ(Status.ACTIVE),
            age=GT(18),
        )
    )
    assert len(filtered) == 2

```

### Trait Modifications

```python
from core_10x.exec_control import CACHE_ONLY
from core_10x.traitable import Traitable, T, M

class Person(Traitable):
    name: str = T()
    age: int = T()

class IdentifiedPerson(Person):
    # Modify existing trait
    name: str = M(T.ID)  # make it an id trait

with CACHE_ONLY():
    person = Person(name='John', age=10, _force=True)
    person2 = IdentifiedPerson(name='John', age=11, _force=True)
    assert person.id()!=person2.id()
```

## Best Practices

### 1. Trait Design

- Use `T()` for traits that need persistence and searching
- Use `RT()` (or omit) for computed traits that shouldn't be stored
- Use `T(T.ID)` for traits that define traitable identity
- Implement getter methods for computed values
- Use setter methods for validation and transformation

### 2. Object Identification

- Design ID traits carefully - they determine global sharing
- Use endogenous traitables for entities that should share state
- Use exogenous traitables for events and records
- Use anonymous traitables for embedded data

## Next Steps

### 1. Explore Examples

- Check out `core_10x/code_samples/` for more examples
- Look at `ui_10x/examples/` for UI integration examples
- Review `core_10x/manual_tests/` for advanced usage patterns

### 2. Run Tests

```bash
# Run unit tests
pytest

# Run specific test suites
pytest core_10x/unit_tests/
pytest ui_10x/unit_tests/
pytest infra_10x/unit_tests/

# Run manual tests (debugging scripts)
python core_10x/manual_tests/trivial_graph_test.py
```

### 3. Build Your Application

- Start with simple traitables and basic traits
- Add ID traits for global sharing when needed
- Implement getter/setter methods as needed
- Use UI components for traitable editing
- Use traitable store for persistence

### 4. Join the Community

- Join our [Discord](https://discord.gg/m7AQSXfFwf) for discussion and support
- Check GitHub Issues for known problems
- Contribute to the project via pull requests

### 5. Advanced Topics

- Enterprise resource management (coming in future releases)

## Resources

- **Documentation**: [README.md](README.md)
- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md)
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)
- **Security**: [SECURITY.md](SECURITY.md)
- **Code of Conduct**: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- **Community**: [Discord](https://discord.gg/m7AQSXfFwf)
- **Contact**: py10x@10xconcepts.com

---
