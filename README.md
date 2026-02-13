# py10x-core

<img src="https://10x-software.org/10x-jerboa.jpeg" alt="Jerboa Logo" width="200">

> **Early preview release – USE AT YOUR OWN RISK. NO WARRANTIES.**

## 🚀 Why py10x?

Standard Python objects are isolated containers. **`py10x-core`** transforms them into a unified, reactive data fabric designed for **10x engineers**:

* **Global Identity:** Objects with matching **ID Traits** share state automatically. Update an object in one module; every other instance reflects that change instantly.
* **Lazy Dependency Graph:** High-performance "pull-based" logic. Recomputations occur on-access, utilizing the graph as a **caching and isolation layer**.
* **Deep Persistence:** Save complex, nested object trees to a **Traitable Store** (MongoDB backend or in-process) with automatic versioning and history tracking.
* **UI-Agnostic:** Define your data and logic once; generate native editors automatically for **Rio** (Web) or **Qt** (Desktop).

---

## 🏁 Hello World

By default, the `Traitable` constructor accepts **only ID traits**. For how the framework uses identity and storage to resolve or create instances, see [How Traitables Are Created](https://github.com/10x-software/py10x/blob/main/GETTING_STARTED.md#how-traitables-are-created) in the Getting Started guide.

```python
from core_10x.traitable import Traitable, T, RT
from core_10x.exec_control import GRAPH_ON, CACHE_ONLY

class Developer(Traitable):
    handle: str = T(T.ID)           # Identity trait
    coffee_cups: int = T(default=0) # Persistent trait
    energy: int = RT()              # Runtime (Lazy) trait

    def energy_get(self) -> int:
        return self.coffee_cups * 20

with CACHE_ONLY(), GRAPH_ON():
    # 1. Constructor identifies the object
    dev = Developer(handle="ghost")
    
    # 2. Assign non-ID traits
    dev.coffee_cups = 5
    
    print(dev.energy)  # 100 (computed on demand)
```

For persistence—**Traitable Store** ([per-class store association](https://github.com/10x-software/py10x/blob/main/GETTING_STARTED.md#per-class-store-association), store unions, and querying—see [Traitable Store](https://github.com/10x-software/py10x/blob/main/GETTING_STARTED.md#traitable-store) in the [Getting Started](https://github.com/10x-software/py10x/blob/main/GETTING_STARTED.md) guide.

---

## 🤝 Contact & Support

* **Getting Started:** [GETTING_STARTED.md](GETTING_STARTED.md) — Full technical manual.
* **Installation:** [INSTALLATION.md](INSTALLATION.md) — Environment setup.
* **Contributing:** [CONTRIBUTING.md](CONTRIBUTING.md) — How to contribute.
* **Discord:** [Join the 10x Community](https://discord.gg/m7AQSXfFwf)
* **Security:** Report vulnerabilities to [security@10x-software.org](mailto:security@10x-software.org)
