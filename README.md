# py10x-core

**Unified, identity-driven, dependency-aware object model for Python**  
—with lazy dependency graph, persistence, automatic UI editors, and more

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](https://opensource.org/licenses/MIT)

<img src="https://10x-software.org/10x-jerboa.jpeg" alt="Jerboa Logo" width="240">

## 🚀 Why py10x?

Standard Python objects have no shared identity layer and no automatic dependency tracking.  
**py10x-core** turns them into a coherent, **dependency-aware graph of connected identifiable objects** — a single shared layer that feels unified across modules, files and processes.

Key superpowers:

- **Global Identity & Sharing**  
  Objects with identical **ID Traits** are automatically the same logical entity.  
  Change a value in one place → every reference sees the update instantly (global cache).

- **Lazy Dependency Graph**  
  Computed traits (derived values) are calculated only when accessed.  
  Dependencies are tracked automatically — no manual invalidation, no recompute storms.

- **Deep Persistence**  
  Complex nested object graphs saved to **Traitable Store** (MongoDB or in-memory).  
  Built-in versioning, history tracking, transparent lazy loading.

- **Automatic UI Editors**  
  Define your data model once → get native two-way editors for **Rio** (web) or **Qt** (desktop).  
  No manual UI code for viewing/editing traitables.

This approach dramatically reduces boilerplate while giving you fine-grained control over computation timing and persistence behavior.

---

## 🏁 Hello World

By default, the `Traitable` constructor accepts **only ID traits**. For how the framework uses identity and storage to resolve or create instances, see [How Traitables Are Created](https://github.com/10x-software/py10x/blob/main/GETTING_STARTED.md#how-traitables-are-created) in the Getting Started guide.

```python
from core_10x.traitable import Traitable, T, RT
from core_10x.exec_control import GRAPH_ON, CACHE_ONLY

class Developer(Traitable):
    handle: str      = T(T.ID)           # ← identity trait → global sharing
    coffee_cups: int = T(default=0)      # persistent
    energy: int      = RT()              # lazy-computed

    def energy_get(self) -> int:
        return self.coffee_cups * 20

# In-memory mode (no storage), dependency graph on.
with CACHE_ONLY(), GRAPH_ON():
    dev = Developer(handle="ghost")
    dev.coffee_cups = 5
    print(dev.energy)           # 100 ← computed lazily on first access

    dev.coffee_cups = 6
    print(dev.energy)           # 120  ← recomputed due to dependency change

    # Same identity → same object
    dev2 = Developer(handle="ghost")
    print(dev2.energy)          # 120  ← shared via global cache
```


Want automatic persistence, per-class stores, store unions, querying, nested objects, UI generation, verifiers, and more?
→ Dive into [GETTING_STARTED.md](https://github.com/10x-software/py10x/blob/main/GETTING_STARTED.md) for the full technical manual.

## 🧠 When Should You Use py10x?

py10x-core is a good fit when:

- Your application has rich domain models with **derived fields**
- You need deterministic **object identity**
- You want automatic dependency tracking
- You want persistence and UI derived from the same model

It may be overkill for simple scripts, stateless APIs, or lightweight validation-only use cases.

If your system has evolving state and relationships, py10x-core removes a large amount of manual synchronization code.

---

## 🔍 How Is This Different?

Unlike `dataclasses` or `Pydantic`:

- Objects have deterministic identity based on **ID traits**
- Identical identity traits resolve to the same logical entity
- Derived fields are lazily computed and dependency-tracked

Unlike traditional ORMs:

- Identity is not tied to a database row
- Persistence is optional and pluggable

Unlike reactive frameworks:

- Dependencies are tracked automatically
- Computation is lazy by default

---

## 🤝 Contact & Support

- **Getting Started:** [GETTING_STARTED.md](https://github.com/10x-software/py10x/blob/main/GETTING_STARTED.md) — Full technical manual.
- **Installation:** [INSTALLATION.md](https://github.com/10x-software/py10x/blob/main/INSTALLATION.md) — Environment setup.
- **Contributing:** [CONTRIBUTING.md](https://github.com/10x-software/py10x/blob/main/CONTRIBUTING.md) — How to contribute.
- **Discord:** [Join the 10x Community](https://discord.gg/m7AQSXfFwf)
- **Security:** Report vulnerabilities to [security@10x-software.org](mailto:security@10x-software.org)
- **Project e-mail:** [py10x@10x-software.org](mailto:py10x@10x-software.org)

