# Getting Started with `py10x-core`

This guide covers the technical implementation and advanced usage of the py10x framework.

## Table of Contents

1. [What is `py10x-core`?](#whats-in-py10x-core)
2. [Installation](#installation)
3. [Core Concepts](#core-concepts)
4. [Your First Traitable](#your-first-traitable)
5. [Object Identification System](#object-identification-system)
6. [Storage and Persistence](#storage-and-persistence)
7. [Dependency Graph and Execution Control](#dependency-graph-and-execution-control)
8. [Traitable Store](#traitable-store)
9. [UI Framework Integration](#ui-framework-integration)
10. [Advanced Features](#advanced-features)
11. [Basket and Bucket Facility](#basket-and-bucket-facility)
12. [Next Steps](#next-steps)

## What's in `py10x-core`?

- **Traitable Framework**: Core data modeling with traits, traitables, and serialization
- **Object Identification**: Endogenous, exogenous, and anonymous traitables with global sharing
- **Dependency Graph**: Automatic computation and dependency tracking
- **Seamless UI Integration**: Rio and Qt6 backends with unified API
- **Storage Integration**: Traitable Store (MongoDB backend or in-process store, e.g. for tests)
- **Built-in Caching**: Automatic trait value and traitable state management

## Installation

### Prerequisites

- Python 3.12 (recommended), 3.11+ supported
- **Traitable Store backend:** `core_10x` tests use the in-process store; `infra_10x` tests use the MongoDB-backed store (where `MongoStore` is implemented). For `infra_10x` tests or persistence examples: local passwordless MongoDB on port 27017.

### Install

```bash
# Install `py10x-core` with UI backend
pip install py10x-core[rio]    # For Rio UI backend
# or
pip install py10x-core[qt]     # For Qt6 backend
```

**For Development**: See [CONTRIBUTING.md](https://github.com/10x-software/py10x/blob/main/CONTRIBUTING.md) for development setup instructions.

## Core Concepts

### Traitables

Traitables are the fundamental data models in `py10x-core`. They are Python classes that inherit from `Traitable` and define typed attributes called "traits".

### Traits

Traits are typed attributes that can be:
- **Regular traits**: Stored and searchable (use `T()`)
- **Runtime traits**: Not stored, computed on-demand (use `RT()` or omit)
- **ID traits**: Define traitable identity for global sharing (use `T(T.ID)` or `RT(T.ID)`)
- **ID_LIKE traits**: Helper traits that participate in ID construction indirectly (use `T(T.ID_LIKE)` or `RT(T.ID_LIKE)`)

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

`py10x-core` provides powerful mechanisms for computed traits, validation, and data transformation:

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
    person = Person(first_name="Alice", last_name="Smith", dob=date(1990, 5, 15), _replace=True)
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
        return self.raw_set_trait_value(trait, value)
    
    def age_set(self, trait, value: int) -> RC:
        """Setter method - validates age range."""
        if value < 0:
            return RC(False, "Age cannot be negative")
        if value > 150:
            return RC(False, "Age cannot exceed 150")
        
        return self.raw_set_trait_value(trait, value)

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

### Verifiers (Validation on verify() and save())

Verifiers are validation methods that run only when `entity.verify()` is called or when the entity is saved (because `save()` calls `verify()` first). Unlike setters, they are **not** run on assignment. Use verifiers for checks that do not need to block assignment (e.g. cross-field or deferred validation).

```python
from core_10x.traitable import Traitable, RT, RC, RC_TRUE

class Example(Traitable):
    code: str = RT()
    limit: int = RT(0)

    def code_verify(self, t, value: str) -> RC:
        """Run on verify() or save(); not on set."""
        if value and not value.isalnum():
            return RC(False, "code must be alphanumeric")
        return RC_TRUE

    def limit_verify(self, t, value: int) -> RC:
        if value is not None and value > 100:
            return RC(False, "limit must be <= 100")
        return RC_TRUE

# Invalid values can be set; verification fails when requested
e = Example()
e.code = "invalid-code"
e.limit = 150
assert e.code == "invalid-code"
assert e.limit == 150

rc = e.verify()
assert not rc  # fails due to code_verify and limit_verify

# Fix and verify
e.code = "valid"
e.limit = 50
e.verify().throw()  # success
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

#### Constructor Parameter: `_replace=True`

The `_replace` parameter controls whether non-ID traits can be provided during traitable initialization and whether existing cached trait values for the same ID are overwritten. By default (`_replace=False`), only ID traits and ID_LIKE traits can be set during construction. When `_replace=True`, non-ID traits can also be provided, and any existing cached values for those traits (for the same ID) are intentionally replaced.

```python
from core_10x.traitable import Traitable, T
from core_10x.exec_control import CACHE_ONLY
from datetime import date

class Person(Traitable):
    # ID traits
    first_name: str = T(T.ID)
    last_name: str = T(T.ID)

    # Non-ID traits (require _replace=True when provided in constructor)
    dob: date = T()
    age: int

    def age_get(self) -> int:
        if not self.dob:
            return 0
        today = date.today()
        return today.year - self.dob.year

# Use _replace=True when providing non-ID traits in constructor
with CACHE_ONLY():
    person = Person(first_name="Alice", last_name="Smith", dob=date(1990, 5, 15), _replace=True)
    assert person.age > 30  # Computed from dob (age depends on current year)
```

**Technical Details:**
- **Construction always creates a new Python instance**: you should compare traitables by `==` (or by `id().value`), not by `is`.
- **Without `_replace=True`**:
  - Only ID traits (`T.ID`) and ID_LIKE traits (`T.ID_LIKE`) can be provided during construction.
  - Attempting to provide non-ID traits raises a `ValueError`.
  - ID is computed from the ID traits (which may themselves be computed from ID_LIKE traits via getters/setters).
- **With `_replace=True`**:
  - All traits can be provided during construction.
  - The initialization process:
    1. Sets ID and ID_LIKE traits first to compute the object ID (for example, an ID getter may derive the ID from ID_LIKE traits).
    2. Clears any existing non-ID trait values cached for the computed ID in the global cache.
    3. Then sets the non-ID traits provided in the constructor in the global cache (any non-ID traits not provided become `XNone`).

**When to use `_replace=True`:**
- When providing non-ID traits during construction.
- When you intentionally want to overwrite existing non-ID trait values for an ID (for example, when recomputing an entity based on updated ID_LIKE inputs).

#### ID_LIKE Traits

ID_LIKE traits participate in ID construction **indirectly** by affecting ID traits through getters or setters, but are not included in the ID calculation directly. A common pattern is:

```python
from core_10x.traitable import Traitable, RT, T

class Cross(Traitable):
    cross: str = RT(T.ID)         # ID trait, e.g. "GBP/USD"
    base_ccy: str = RT(T.ID_LIKE)  # helper traits
    quote_ccy: str = RT(T.ID_LIKE)

    def cross_get(self) -> str:
        return f'{self.base_ccy}/{self.quote_ccy}'
```

Here `base_ccy` and `quote_ccy` are ID_LIKE traits; changing them changes the `cross` ID trait value via the getter, and thus the logical identity, even though only `cross` is marked as `T.ID`. They can be set during initialization without requiring `_replace=True` because they are often needed to compute the actual ID traits.

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
    record = DataRecord(name="sensor_001", data=AnonymousData(value="temp: 72.5", timestamp=1234567890.0), _replace=True)
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

### Traitable Store and persistence

The framework uses a **Traitable Store** for persistence. Implementations include the MongoDB-backed store (`MongoStore`, in `infra_10x`) and an in-process store (used by `core_10x` tests). Example with the MongoDB backend:

```python
from datetime import date
from infra_10x.mongodb_store import MongoStore
from core_10x.code_samples.person import Person

# Connect to a Traitable Store (MongoDB backend)
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
To persist a traitable and all of its referenced objects (including self-references), use `person.save(save_references=True)`.

### Connecting to stores

You can connect to a store in three ways:

1. **Direct instance:** `MongoStore.instance(hostname='localhost', dbname='myapp')`
2. **URI:** `TsStore.instance_from_uri('mongodb://localhost/myapp')` (from `core_10x.ts_store`)
3. **Environment variable:** Set `XX_MAIN_TS_STORE_URI` to define a default global store used by all storable traitables.

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
    company = Company(name="Acme Corp", founded_year=2020, _replace=True)
    employee = Employee(first_name="Alice", last_name="Smith", company=company, _replace=True)
    
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
        _replace=True
    )
    
    # The address is stored embedded within the person
    assert person.serialize_object()['address'] == {'street': '123 Main St', 'city': 'Anytown', 'zip_code': '12345'}
```

## Execution Modes and Control

`py10x-core` provides fine-grained control over computation and execution through execution modes. Each mode has specific overhead and benefits that should be considered based on your use case.

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
            == f"""Failed in <class '__doc_test_GETTING_STARTED__.Calculator'>.sum.sum_get
    object = {calc.id_value()};
original exception = TypeError: can only concatenate str (not "int") to str"""
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

### Per-class store association

You can associate particular Traitable classes (or modules) with specific store instances. When `use_ts_store_per_class` is enabled, the framework resolves the store for a class via `TsClassAssociation` and `NamedTsStore` (create and persist those traitables in your main store so each class or module maps to a logical store name and URI). This allows different Traitable subclasses to use different stores (e.g. different MongoDB databases or backends).

### Storage Context and Traitable Creation

Storage context is required for traitable creation because the constructor needs to:
1. Construct the ID from ID traits
2. Look for existing instances in memory and storage
3. Set additional trait values if no shared instance is found

```python
from infra_10x.mongodb_store import MongoStore
from core_10x.traitable import Traitable, T
from datetime import date

class Person(Traitable, keep_history=False):
    first_name: str = T(T.ID)
    last_name: str = T(T.ID)
    dob: date = T()

# Storage context is required for traitable creation
with MongoStore.instance(hostname="localhost", dbname="myapp"):
    # Constructor uses storage to find existing instances
    person = Person(first_name="Alice", last_name="Smith")
    person.dob = date(1990, 5, 15)
    person.save()  # Persists to the traitable store
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

class Person(Traitable, keep_history=False):
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

#### Traitable Store integration

```python
from core_10x.traitable import Traitable, T
from datetime import date
from infra_10x.mongodb_store import MongoStore

class Person(Traitable,keep_history=False):
    first_name: str = T(T.ID)
    last_name: str = T(T.ID)
    dob: date = T()
    
# Connect to a Traitable Store (MongoDB backend in this example)
with MongoStore.instance(hostname="localhost", dbname="myapp"):
    person = Person(first_name="Alice", last_name="Smith")
    person.dob = date(1990, 5, 15)
    person.save()  # Persists to the traitable store
```

## UI Framework Integration

`py10x-core` provides seamless UI framework switching between Rio and Qt6 with specialized components for traitable editing:

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

`py10x-core` provides powerful named constant systems for type-safe enumerations and flags:

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

#### Lookup by name

`NamedConstant.item(symbol_name)` returns the constant for a given string key, or `None` if not found — useful when deserializing values from external sources:

```python
from core_10x.named_constant import Enum

class Priority(Enum, seed=1):
    LOW = ()
    MEDIUM = ()
    HIGH = ()

assert Priority.item('HIGH') is Priority.HIGH
assert Priority.item('UNKNOWN') is None
```

#### Named Callables

`NamedCallable` is a `NamedConstant` whose values are callables.  Each member wraps a function that can be stored, compared, and serialized by name.

```python
from core_10x.named_constant import NamedCallable

class Aggregator(NamedCallable):
    SUM  = lambda items: sum(items)
    MEAN = lambda items: sum(items) / len(items)

assert Aggregator.SUM([1, 2, 3]) == 6
assert Aggregator.MEAN([1, 2, 3]) == 2.0
```

For one-off wrapping of an anonymous callable (e.g. inside a factory method that accepts a plain `lambda`) use `NamedCallable.just_func`:

```python
from core_10x.named_constant import NamedCallable

double = NamedCallable.just_func(lambda x: x * 2)
assert double(5) == 10
```

#### NamedConstantValue and NamedConstantTable

`NamedConstantValue` maps every member of a `NamedConstant` class to an associated value, giving attribute-style access by constant name or by the constant itself.

```python
from core_10x.named_constant import NamedConstant, NamedConstantValue

class Color(NamedConstant):
    RED   = ()
    GREEN = ()
    BLUE  = ()

palette = NamedConstantValue(Color, RED='#FF0000', GREEN='#00FF00', BLUE='#0000FF')

assert palette[Color.RED]   == '#FF0000'
assert palette['GREEN']     == '#00FF00'
assert palette.BLUE         == '#0000FF'
```

`NamedConstantTable` extends `NamedConstantValue` to a two-dimensional structure: each *row* is keyed by one `NamedConstant` class and each *column* by another.  Rows are tuples whose elements are looked up by column constant.

```python
from core_10x.named_constant import NamedConstant, NamedConstantTable

class Asset(NamedConstant):
    CASH   = ()
    EQUITY = ()
    BOND   = ()

class Attr(NamedConstant):
    RISK_WEIGHT = ()
    LIQUID      = ()

table = NamedConstantTable(
    Asset, Attr,
    CASH   = (0.0,  True),
    EQUITY = (1.0,  True),
    BOND   = (0.5, False),
)

assert table[Asset.EQUITY][Attr.RISK_WEIGHT] == 1.0
assert table['CASH']['LIQUID'] is True
assert table.primary_key(Attr.LIQUID, False) is Asset.BOND
```

`NamedConstantTable.extend` creates a new table that adds rows from a *subclass* of the row constant, preserving all existing rows:

```python
from core_10x.named_constant import NamedConstant, NamedConstantTable

class BaseAsset(NamedConstant):
    CASH   = ()
    EQUITY = ()

class Attr(NamedConstant):
    RISK_WEIGHT = ()

base_table = NamedConstantTable(BaseAsset, Attr, CASH=(0.0,), EQUITY=(1.0,))

class ExtAsset(BaseAsset):
    COMMODITY = ()

ext_table = base_table.extend(ExtAsset, COMMODITY=(0.8,))

assert ext_table[ExtAsset.CASH][Attr.RISK_WEIGHT]      == 0.0
assert ext_table[ExtAsset.COMMODITY][Attr.RISK_WEIGHT] == 0.8
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

class Person(Traitable,keep_history=False):
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

class Person(Traitable,keep_history=False):
    name: str = T()
    age: int = T()

class IdentifiedPerson(Person):
    # Modify existing trait
    name: str = M(T.ID)  # make it an id trait

with CACHE_ONLY():
    person = Person(name='John', age=10, _replace=True)
    person2 = IdentifiedPerson(name='John', age=11, _replace=True)
    assert person.id()!=person2.id()
```

## Basket and Bucket Facility

The **Basket / Bucket** facility provides a composable, aggregation-ready container
for any collection of `Traitable` objects.  It separates *how objects are grouped*
(via `Bucketizer` strategies) from *what is computed on the groups* (via aggregator
callables), and works naturally with the trait dependency graph.

### Core Concepts

| Term | What it is |
|------|-----------|
| `Bucket` | An atomic container that holds `(member, qty)` pairs. Three shapes — see [Bucket shapes](#bucket-shapes) below. |
| `Basket` | A higher-level container that owns one or more `Bucket` instances, routes incoming objects into the correct bucket via `Bucketizer` strategies, and exposes aggregation via trait lifting. |
| `Bucketizer` | A strategy object that maps each object to a *bucket tag*.  Four factory methods: `by_class`, `by_feature`, `by_range`, `by_breakpoints`. |
| `Basketable` | A mixin for `Traitable` types that contain other `Traitable` objects (e.g. a `Portfolio` that holds `Position`s): implement `members_qtys()` so that `contents(basket)` can recursively walk the hierarchy and deposit the leaf objects — with accumulated quantities — into a `Basket` — see [Basketable](#basketable--hierarchical-traversal). |

### Quick Start

Create a `Basket`, add objects, then split them into named groups with a `Bucketizer`:

```python
from core_10x.basket import Basket, Bucketizer
from core_10x.exec_control import CACHE_ONLY
from core_10x.traitable import Traitable, T

class Animal(Traitable):
    name: str = T(T.ID)
    weight: float = T()
    species: str = T()

with CACHE_ONLY():
    fido = Animal(name='fido')
    fido.weight = 20.0
    fido.species = 'canine'

    kitty = Animal(name='kitty')
    kitty.weight = 4.0
    kitty.species = 'feline'

    # Step 1 — collect objects into a basket (no bucketing yet)
    basket = Basket(base_class=Animal)
    basket.add(fido)
    basket.add(kitty, qty=2.0)  # qty lets you weight members

    for member, qty in basket.the_bucket.members_qtys():
        print(member.name, qty)
    # fido 1.0 / kitty 2.0

    # Step 2 — add a bucketizer to split members by weight range
    # Animal.T.weight is a ClassTrait — equivalent to lambda a: a.weight but serializable
    bz = Bucketizer.by_range(Animal, Animal.T.weight,
                             ['light', 0.0, 10.0],
                             ['heavy', 10.0, 1e9])
    basket.bucketizers = [bz]
    basket.add(fido)
    basket.add(kitty, qty=2.0)

    for tag, bucket in basket.tags_buckets():
        names = [m.name for m in bucket.members()]
        print(tag, '->', names)
    # ('heavy',) -> ['fido'] / ('light',) -> ['kitty']
```

### Bucket shapes

Each physical `Bucket` (`BucketDict`, `BucketSet`, or `BucketList`) stores **who** is in the bucket and **how much** of each member. The shape fixes **how members are keyed** and **how quantities combine** when you insert the same logical member again.

| Shape | Implementation | Same `Traitable` added twice | Order preserved? | Typical use |
|-------|----------------|------------------------------|------------------|-------------|
| **`BUCKET_SHAPE.DICT`** (`BucketDict`, **default** for `Basket`) | `dict[Traitable, float]` | Quantities **add** (e.g. two adds of the same position → one row, larger qty) | Yes (insertion order) | **Risk / P/L** style: weighted holdings, lot sizes, net exposure per instrument |
| **`BUCKET_SHAPE.SET`** (`BucketSet`) | `set` | Second insert is a no-op; each member appears **once** with reported qty **1.0** | No | **Membership** only: “which names appear under this book?” without caring about weight |
| **`BUCKET_SHAPE.LIST`** (`BucketList`) | `list` | **Duplicate entries** allowed; each insert appends with qty **1.0** (qty parameter is ignored) | Yes (insertion order) | **Explicit duplicates**: two legs of a trade referencing the same instrument kept as separate rows; any workflow where the same object must occupy multiple positions in a sequence |

> **`DICT` and `LIST` vs `SET`:** `DICT` and `LIST` both preserve insertion order and support meaningful quantity-based aggregation — `DICT` accumulates fractional quantities per unique member, `LIST` counts each insertion as a separate row with qty 1.0. The distinction between them is merge behavior: `DICT` folds repeated inserts into one entry (summing quantities), `LIST` keeps them as independent rows. `SET` is different from both: it is a pure membership tracker — quantities are always 1.0, repeated inserts are no-ops, and order is not preserved.

**Choosing a shape:** use **DICT** whenever quantities must aggregate per identity (the common case); use **SET** when you only need unique membership; use **LIST** only when the same object must appear as multiple independent entries.

**Where the shape is set**

1. **`Basket` subclass** — `class MyBasket(Basket, bucket_shape=BUCKET_SHAPE.SET): ...`
2. **Default** — plain `Basket(...)` uses **DICT**.
3. **`Basketable` mixin on the content class** — if the content class itself mixes in `Basketable` and declares `bucket_shape=...`, any `Basket` whose `base_class` is that class automatically uses the same shape — see [Basket subclass vs Basketable mixin](#basket-subclass-vs-basketable-mixin) below.

Example: behavior of the three bucket types on the same member:

```python
from core_10x.basket import BucketDict, BucketList, BucketSet
from core_10x.exec_control import CACHE_ONLY
from core_10x.traitable import Traitable, T

class Lot(Traitable):
    name: str = T(T.ID)

with CACHE_ONLY():
    x = Lot(name='XYZ')

    d = BucketDict()
    d._insert(x, 2.0)
    d._insert(x, 1.0)
    assert dict(d.members_qtys())[x] == 3.0  # summed

    s = BucketSet()
    s._insert(x, 1.0)
    s._insert(x, 999.0)  # still one member; set semantics
    assert len(list(s.members_qtys())) == 1

    lst = BucketList()
    lst._insert(x, 1.0)
    lst._insert(x, 1.0)
    assert len(list(lst.members_qtys())) == 2  # two members
```

### Bucketizers

Without a bucketizer every member lands in a single `the_bucket`.  A `Bucketizer` adds a
grouping dimension: it maps each incoming object to a *tag*, and the basket maintains one
`Bucket` per distinct tag.  You then iterate over `(tag, bucket)` pairs with `tags_buckets()`,
or use trait lifting to get per-tag aggregated results.

```python
from core_10x.basket import Basket, Bucketizer
from core_10x.exec_control import CACHE_ONLY
from core_10x.traitable import Traitable, T

class Animal(Traitable):
    name: str = T(T.ID)
    weight: float = T()
    species: str = T()

with CACHE_ONLY():
    fido = Animal(name='fido')
    fido.species = 'canine'
    kitty = Animal(name='kitty')
    kitty.species = 'feline'

    basket = Basket(base_class=Animal)
    bz = Bucketizer.by_feature(Animal, Animal.T.species)
    basket.bucketizers = [bz]

    basket.add(fido)
    basket.add(kitty)

    for tag, bucket in basket.tags_buckets():
        print(tag, [m.name for m in bucket.members()])
    # ('canine',)  ['fido']
    # ('feline',)  ['kitty']
```

Multiple bucketizers produce *compound tuple keys* — one element per bucketizer, in order:

```python
from core_10x.basket import Basket, Bucketizer
from core_10x.exec_control import CACHE_ONLY
from core_10x.traitable import Traitable, T
from core_10x.xinf import XInf

class Animal(Traitable):
    name: str = T(T.ID)
    weight: float = T()

class Dog(Animal):
    breed: str = T()

with CACHE_ONLY():
    basket = Basket(base_class=Animal)
    bz1 = Bucketizer.by_class(Animal)
    bz2 = Bucketizer.by_range(Animal, Animal.T.weight, ['light', 0, 50], ['heavy', 50, XInf])
    basket.bucketizers = [bz1, bz2]
    # Example tag shape: (Dog, 'heavy'), (Dog, 'light'), ...
```

#### Factory methods


#### `by_class` — split on the Python class

```python
from core_10x.basket import Bucketizer
from core_10x.exec_control import CACHE_ONLY
from core_10x.traitable import Traitable, T

class Animal(Traitable):
    name: str = T(T.ID)

class Dog(Animal):
    breed: str = T()

class Cat(Animal):
    indoor: bool = T()

with CACHE_ONLY():
    bz = Bucketizer.by_class(Animal)  # tag = exact class
    bz = Bucketizer.by_class(Animal, Dog, Cat)  # only Dog/Cat pass; others excluded
```

#### `by_feature` — split on an arbitrary callable

The second argument can be either a **`ClassTrait`** (`Animal.T.species`) or a **plain callable** (lambda / named function).  Prefer `ClassTrait` for direct trait reads — it carries the trait name and is fully serializable, so a `Basket` with such a `Bucketizer` can be stored and reloaded.  Use a lambda or `NamedCallable` only when the feature is a computed value that cannot be expressed as a single trait read.

```python
from core_10x.basket import Bucketizer
from core_10x.exec_control import CACHE_ONLY
from core_10x.traitable import Traitable, T

class Animal(Traitable):
    name: str = T(T.ID)
    weight: float = T()
    species: str = T()

with CACHE_ONLY():
    # Preferred: ClassTrait — serializable, equivalent to lambda a: a.species
    bz = Bucketizer.by_feature(Animal, Animal.T.species)
    bz = Bucketizer.by_feature(Animal, Animal.T.species, 'canine', 'feline')

    # Lambda still needed for computed / derived values
    bz = Bucketizer.by_feature(
        Animal,
        Animal.T.weight,
        bucket_tag_calc=lambda w: 'heavy' if w > 50 else 'light',
    )
```

#### `by_range` — split on numeric ranges

Each range spec is either a `list` (inclusive upper bound) or `tuple`
(exclusive upper bound).  Use `XInf` for positive infinity and `-XInf` for negative infinity.

```python
from core_10x.basket import Bucketizer
from core_10x.exec_control import CACHE_ONLY
from core_10x.traitable import Traitable, T
from core_10x.xinf import XInf

class Animal(Traitable):
    name: str = T(T.ID)
    weight: float = T()

with CACHE_ONLY():
    bz = Bucketizer.by_range(
        Animal,
        Animal.T.weight,            # ClassTrait — serializable; lambda a: a.weight also works
        ('underweight', 0.0, 18.5),  # 0 <= w < 18.5
        ['normal', 18.5, 25.0],      # 18.5 <= w <= 25.0
        ['overweight', 25.0, XInf],  # 25.0 <= w <= inf
    )
```

#### `by_breakpoints` — split on sorted breakpoints

A compact alternative to `by_range` when all intervals are contiguous.  Each pair of adjacent breakpoints defines a **half-open `[low, high)` interval**: the lower bound is included, the upper bound is excluded, and a value exactly on a boundary belongs to the interval where it is the *lower* bound.  The only exception is the last interval when `include_last=True`, which becomes `[low, high]`.

```python
from core_10x.basket import Bucketizer
from core_10x.exec_control import CACHE_ONLY
from core_10x.traitable import Traitable, T
from core_10x.xinf import XInf

class Animal(Traitable):
    name: str = T(T.ID)
    weight: float = T()

with CACHE_ONLY():
    # Two half-open intervals [0, 18.5) and [18.5, 25.0); values >= 25.0 → not bucketed
    bz = Bucketizer.by_breakpoints(Animal, Animal.T.weight, 0.0, 18.5, 25.0)

    # Add XInf to capture all values >= 25.0 in a third interval [25.0, ∞)
    bz = Bucketizer.by_breakpoints(Animal, Animal.T.weight, 0.0, 18.5, 25.0, XInf)

    # include_last=True closes the last finite interval: [18.5, 25.0]
    # Raises an error when the last breakpoint is XInf (no real value equals ∞)
    bz = Bucketizer.by_breakpoints(Animal, Animal.T.weight, 0.0, 18.5, 25.0, include_last=True)
```

### Adding a Bucketizer Incrementally

`add_bucketizer` re-partitions already-added members without requiring a rebuild:

```python
from core_10x.basket import Basket, Bucketizer
from core_10x.exec_control import CACHE_ONLY
from core_10x.traitable import Traitable, T
from core_10x.xinf import XInf

class Animal(Traitable):
    name: str = T(T.ID)
    weight: float = T()

with CACHE_ONLY():
    fido = Animal(name='fido')
    fido.weight = 10.0
    kitty = Animal(name='kitty')
    kitty.weight = 60.0

    basket = Basket(base_class=Animal)
    basket.add(fido)
    basket.add(kitty)

    bz = Bucketizer.by_range(Animal, Animal.T.weight, ['light', 0, 50], ['heavy', 50, XInf])
    basket.add_bucketizer(bz)  # re-distributes members into the new buckets
```

Objects that do not match the new bucketizer's tags are silently dropped from
the re-partitioned basket.

### Trait Lifting and Aggregation

Accessing a trait name directly on a `Basket` *lifts* it across all members.  The return value depends on whether an `aggregator_class` is set:

| `aggregator_class` | No bucketizers | With bucketizers |
|--------------------|---------------|-----------------|
| **Provided** — member named after the trait (`AGG.WEIGHT` for `basket.weight`) | single aggregated value | `{tag: aggregated_value}` per bucket |
| **Not provided** | generator of `(value, qty)` pairs | `{tag: generator of (value, qty) pairs}` per bucket |

The aggregator callable receives a generator of `(value, qty)` tuples and returns a single value.

```python
from core_10x.basket import Basket, Bucketizer
from core_10x.exec_control import CACHE_ONLY
from core_10x.named_constant import NamedCallable
from core_10x.traitable import Traitable, T
from core_10x.xinf import XInf

class Animal(Traitable):
    name: str = T(T.ID)
    weight: float = T()

class AGG(NamedCallable):
    WEIGHT = lambda gen: sum(v * q for v, q in gen)

with CACHE_ONLY():
    fido = Animal(name='fido')
    fido.weight = 10.0
    kitty = Animal(name='kitty')
    kitty.weight = 5.0

    # With aggregator: returns a single aggregated value
    basket = Basket(base_class=Animal, aggregator_class=AGG)
    basket.add(fido, 1.0)
    basket.add(kitty, 2.0)
    total_weight = basket.weight  # AGG.WEIGHT((10.0,1.0),(5.0,2.0)) → 20.0

    # Without aggregator: returns a generator of (value, qty) pairs
    basket2 = Basket(base_class=Animal)
    basket2.add(fido, 1.0)
    basket2.add(kitty, 2.0)
    pairs = list(basket2.weight)  # [(10.0, 1.0), (5.0, 2.0)]
```

If `bucketizers` are set, each return value above is wrapped in a `{tag: ...}` dict, one entry per bucket.

### Basketable — Hierarchical Traversal

`Basketable` is a mixin for `Traitable` classes that form a **containment hierarchy** — think a portfolio that holds sub-portfolios and books, each book holds trades, each trade holds instruments.  It lets you extract all instances of any node type from an arbitrary point in the tree with a single `contents(basket)` call, accumulating quantities as they propagate down.

Only **intermediate nodes** need to mix in `Basketable`.  Leaf nodes — objects that are directly collected into the basket — are plain `Traitable` classes and require no special treatment.

**Protocol** — two methods to implement on each intermediate node:

| Method | Purpose |
|--------|---------|
| `members_qtys()` | Yield `(child, qty)` pairs for this node's direct children |
| `is_member(obj)` | Return `True` if `obj` is a direct child of this node (optional — not called during `contents()` traversal) |

**Traversal rule** — `contents(basket, qty=1.0)` iterates `members_qtys()`.  For each `(child, child_qty)`:
- if `child` is an instance of `basket.base_class` → `basket.add(child, qty × child_qty)`
- otherwise → recurse: `child.contents(basket, qty × child_qty)`

Quantities **multiply down the path**, so a book with weight 0.5 in a portfolio scales all of its instrument positions by that factor.

Every intermediate node must be `Basketable`; if traversal reaches an object that is neither the target type nor `Basketable`, an error is raised.

```python
import itertools

from core_10x.basket import Basket, Basketable, BUCKET_SHAPE
from core_10x.exec_control import CACHE_ONLY
from core_10x.traitable import Traitable, T, RT


# Leaf node — plain Traitable, no Basketable needed.
class Instrument(Traitable):
    ticker: str   = T(T.ID)
    price:  float = T()


# Trade owns a basket of instruments and delegates traversal to it.
class Trade(Traitable, Basketable, bucket_shape=BUCKET_SHAPE.DICT):
    name:        str    = T(T.ID)
    instruments: Basket = T()

    def members_qtys(self):
        return self.instruments.members_qtys()
    
    def is_member(self, obj: Basketable) -> bool:
        if self.instruments.all_buckets:
            return any(bucket.is_member(obj) for bucket in self.instruments.all_buckets.values())
        return self.instruments.the_bucket.is_member(obj)

# Book resolves its trades by name via a RT getter that returns a Basket of Trades.
class Book(Traitable, Basketable, bucket_shape=BUCKET_SHAPE.SET):
    name:        str    = T(T.ID)
    trade_names: list   = T()
    trades:      Basket = RT()

    def trades_get(self) -> Basket:
        basket = Basket(base_class=Trade)
        for n in self.trade_names:
            basket.add(Trade.existing_instance(name=n))
        return basket

    def members_qtys(self):
        return self.trades.members_qtys()

    def is_member(self, obj) -> bool:
        return self.trades.is_member(obj)


# Portfolio holds sub-portfolios and books in two separate Basket traits.
# members_qtys chains both so contents() traverses all branches.
class Portfolio(Traitable, Basketable, bucket_shape=BUCKET_SHAPE.SET):
    name:            str    = T(T.ID)
    book_names:      list   = T()
    portfolio_names: list   = T()
    books:           Basket = RT()
    portfolios:      Basket = RT()

    def books_get(self) -> Basket:
        basket = Basket(base_class=Book)
        for n in self.book_names:
            basket.add(Book.existing_instance(name=n))
        return basket

    def portfolios_get(self) -> Basket:
        basket = Basket(base_class=Portfolio, subclasses_allowed=False)
        for n in self.portfolio_names:
            basket.add(Portfolio.existing_instance(name=n))
        return basket

    def members_qtys(self):
        return itertools.chain(self.portfolios.members_qtys(), self.books.members_qtys())
    
    def is_member(self, obj) -> bool:
        return self.books.is_member(obj) or self.portfolios.is_member(obj)


with CACHE_ONLY():
    aapl = Instrument(ticker='AAPL')
    aapl.price = 189.0
    msft = Instrument(ticker='MSFT')
    msft.price = 420.0

    # Trade holds instruments in an embedded Basket (no specialized subclass needed).
    t1 = Trade(name='T1')
    t1.instruments = Basket(base_class=Instrument)
    t1.instruments.add(aapl, 10.0)
    t1.instruments.add(msft, 5.0)

    # Book references trades by name; the getter resolves them on access.
    book = Book(name='Equities')
    book.trade_names = ['T1']

    # Sub-portfolio P1 owns the equity book.
    p1 = Portfolio(name='P1')
    p1.book_names      = ['Equities']
    p1.portfolio_names = []

    # Top-level portfolio aggregates sub-portfolios (and could hold books directly too).
    top = Portfolio(name='Top')
    top.portfolio_names = ['P1']
    top.book_names      = []

    # Walk Top → P1 → Equities → T1 → Instrument, multiplying quantities at each level.
    instr_basket = Basket(base_class=Instrument)
    top.contents(instr_basket)

    qtys = dict(instr_basket.the_bucket.members_qtys())
    assert qtys[aapl] == 10.0
    assert qtys[msft] == 5.0
    
    assert p1.is_member(book)
    assert book.is_member(t1)
    assert t1.is_member(aapl)
    
    # Stop at Trade level — traversal does not descend further into Instruments.
    trade_basket = Basket(base_class=Trade)
    top.contents(trade_basket)
    assert trade_basket.is_member(t1)


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

- **Documentation**: [README.md](https://github.com/10x-software/py10x/blob/main/README.md)
- **Contributing**: [CONTRIBUTING.md](https://github.com/10x-software/py10x/blob/main/CONTRIBUTING.md)
- **Changelog**: [CHANGELOG.md](https://github.com/10x-software/py10x/blob/main/CHANGELOG.md)
- **Security**: [SECURITY.md](https://github.com/10x-software/py10x/blob/main/SECURITY.md)
- **Code of Conduct**: [CODE_OF_CONDUCT.md](https://github.com/10x-software/py10x/blob/main/CODE_OF_CONDUCT.md)
- **Community**: [Discord](https://discord.gg/m7AQSXfFwf)
- **Contact**: py10x@10x-software.org

---
