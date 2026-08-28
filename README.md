# py10x-core

**The Substratum of 10x Genaxy** — a generative core for software, not a feature list.

[![Python 3.11–3.13](https://img.shields.io/badge/python-3.11–3.13-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](https://opensource.org/licenses/MIT)

<img src="https://10x-software.org/10x-jerboa.jpeg" alt="Jerboa Logo" width="240">

## 🌌 Why Genaxy?

**10x** is the concept: never rebuild the same foundation twice. A **genaxy** is the kind of system that makes that possible — built around a small core rather than assembled feature by feature. **10x Genaxy** is this one. This package (`py10x-core`) is its **substratum**.

The **substratum** is that core: a handful of laws (principles), not a feature set. Today those are identity, dependency, persistence, and presentation; more may join them. Everything else follows from these. They aren't a checklist to memorize — they're vocabulary for describing a real-world problem, before any specific technology gets chosen.

That core is **generative**: you describe the entity — what it is, what it depends on, where it is stored, how it should be presented and interacted with — and the application, the report, the service you needed falls out of that description, largely for free.

Around the substratum sit **subject domains** — real fields of work, each built on the same core instead of reinventing it. Finance is the first (`py10x-fin-base`). More will follow. Domains surround the substratum the way planets surround a star — independent, distinct, but held by the same laws.

Most software is built domain-first: a finance system, a healthcare system, a logistics system — each reinventing identity, persistence, and UI from scratch. Genaxy inverts that. Build the substratum once. Let every domain grow from it.

10x Genaxy isn't the first genaxy — SecDb, Athena, and others came before it (See [lineage](LINEAGE.md)).

In this README:

- **Identity & sharing** — same ID traits, same entity ([nine lines](#-identity-and-dependency-in-nine-lines))
- **Lazy dependency graph** — computed traits, tracked automatically ([nine lines](#-identity-and-dependency-in-nine-lines))
- **Resources and persistence** — URI-addressed Traitable Store over MongoDB, PostgreSQL, DuckDB ([resources](#-everything-is-a-resource))
- **Credential vault** — one registration, no passwords in application code ([resources](#-everything-is-a-resource))
- **Derived UI** — Qt or Rio editors from the class ([UI](#-the-ui-is-derived-not-written))

---

## 🏁 Identity and Dependency, in Nine Lines

By default, the `Traitable` constructor accepts **only ID traits**. For how the framework uses identity and storage to resolve or create instances, see [How Traitables Are Created](https://github.com/10x-software/py10x/blob/main/GETTING_STARTED.md#how-traitables-are-created) in the Getting Started guide.

```python
from core_10x.traitable import Traitable, T, RT
from core_10x.exec_control import GRAPH_ON, CACHE_ONLY

class Developer(Traitable):
    handle: str      = T(T.ID)           # ← identity trait → global sharing
    coffee_cups: int = T(default=0)      # persistent
    energy: int      = RT()              # runtime-only (not stored)

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

Two of the four laws, in nine lines: `handle` is the *identity*, `energy` is a *dependency* on `coffee_cups`, tracked and recomputed automatically.

---

## 🗄️ Everything Is a Resource

Real systems rarely live in one database. 10x Genaxy treats every external dependency — a MongoDB cluster, a Postgres box, a DuckDB file, a credentials vault — as a `Resource`: addressed by a plain URI, resolved to a concrete driver through a small, pluggable registry. The Traitable Store you persist objects to is just one kind of `Resource`, alongside anything else your system depends on.

You define **logical** resources — names your code refers to, like `"main"` or `"mkt_data"` — and assign each one to a **physical** location (an actual URI) separately, per environment. Traitable classes associate themselves with a logical resource by name, so different parts of a system can live on different physical stores without any downstream code needing to know or care which.

Authentication follows the same shape. A user registers once: an RSA keypair is generated on their own machine, the private key is encrypted with their own master password, and everything lands in the OS keyring — never transmitted, never stored in plaintext. From that point on, every resource that user is entitled to just works, with no per-database credential wiring anywhere in application code.

### Traitable Store

A Traitable Store is the Resource that persists objects. `Traitable.store_from_uri` opens it by URI and fills in credentials from the vault when the server requires them — no passwords in application code. MongoDB, PostgreSQL, and DuckDB are the same pattern:

```python
from datetime import date
from core_10x.code_samples.person import Person
from core_10x.traitable import Traitable

with Traitable.store_from_uri("mongodb://localhost/myapp"):
    person = Person(first_name="Alice", last_name="Smith")
    person.dob = date(1990, 5, 15)
    person.save()
```

Identity still holds across the store: constructing `Person(first_name="Alice", last_name="Smith")` later resolves to the stored instance. Versioning, history, per-class stores, querying, and nested graphs are in [Traitable Store](GETTING_STARTED.md#traitable-store) in the Getting Started guide.


---

## 🎨 The UI Is Derived, Not Written

Presentation is the fourth law, and it works the same way: describe the shape of the thing, and the UI for viewing and editing it comes for free. A dropdown that only accepts valid values isn't a widget you configure — it falls out of typing the trait as a `NamedConstant`:

```python
from core_10x.traitable import Traitable, RT, Ui
from ui_10x.examples.constants import COLOR, FONT

class StyleSheet(Traitable):
    foreground: COLOR   = RT(COLOR.LIGHTGREEN)
    background: COLOR   = RT(COLOR.BLACK,   ui_hint = Ui(flags = Ui.SEPARATOR))

    font: FONT          = RT(FONT.HELVETICA)
    italic: bool        = RT(True,          ui_hint = Ui('italic',  right_label = True))
    bold: bool          = RT(False,         ui_hint = Ui('bold',    right_label = True, flags = Ui.SEPARATOR))

    border: bool        = RT(True)
    border_color: COLOR = RT(COLOR.BLUE)
    border_width: int   = RT(2,             ui_hint = Ui(flags = Ui.SEPARATOR))

    show_me: str        = RT('This is how it will look...',  ui_hint = Ui('WYSIWYG', min_width = 50))

    def show_me_style_sheet(self) -> dict:
        return {
            Ui.FG_COLOR:        self.foreground.value,
            Ui.BG_COLOR:        self.background.value,
            Ui.FONT:            self.font.value,
            Ui.FONT_STYLE:      'italic'   if self.italic   else 'normal',
            Ui.FONT_WEIGHT:     'bold'     if self.bold     else 'normal',
            Ui.BORDER_WIDTH:    f'{self.border_width}px',
            Ui.BORDER_STYLE:    'solid'    if self.border   else '',
            Ui.BORDER_COLOR:    self.border_color.value,
        }
```

That's the entire program — no layout code, no widget wiring, no dropdown population logic. `TraitableEditor(StyleSheet()).popup()` generates the full dialog below: dropdowns, checkboxes, and a live preview that updates itself, because it's just another computed trait sharing the same dependency graph as everything else.

<img src="Screenshot_style_sheet.jpg" alt="The entire StyleSheet trait class (left) and the auto-generated editor it produces (right) — the WYSIWYG preview updates live from the dependency graph, with no manual UI code anywhere." width="1000">

The same class definition renders as a native Qt desktop dialog or a Rio web view, depending only on which backend is active.

---

## 🧭 When Should You Build a Subject Domain of 10x Genaxy?

10x Genaxy fits problems with:

- Real-world entities with derived, computed state
- A need for deterministic, shared identity across a whole system
- Data that outlives a single process — persistence you don't want to hand-roll
- A UI that should never drift out of sync with the model it displays

It's overkill for a simple script, a stateless API, or pure validation logic — those don't need a substratum, they need a function. 10x Genaxy pays off when a system's state and relationships keep evolving, and keeping everything in sync by hand is the actual cost center.

---

## 🔍 How Is This Different?

Compared to `dataclasses` or Pydantic — objects have deterministic identity from their ID traits; the same identity always resolves to the same logical entity; derived fields are lazily computed and dependency-tracked, not just validated once at construction.

Compared to traditional ORMs — identity isn't tied to a database row, and persistence is optional and pluggable per class, not baked into one schema.

Compared to reactive frameworks — dependencies are tracked automatically, computation is lazy by default, and the same graph drives persistence and UI, not just view updates.

---

## Documentation map

| I want to… | Read |
|------------|------|
| Read the full vision and history | [LINEAGE.md](LINEAGE.md) |
| Install py10x | [INSTALLATION.md](INSTALLATION.md) |
| Learn the Traitable framework | [GETTING_STARTED.md](GETTING_STARTED.md) |
| Install / use the first subject domain of 10x Genaxy (`xxfin`) | [xx_fin/README.md](xx_fin/README.md) |
| Contribute code | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Cut a release / sync dev deps | [dev_10x/README.md](dev_10x/README.md) |

## 🤝 Contact & Support

- **Project e-mail:** [py10x@10x-software.org](mailto:py10x@10x-software.org)
- **Security:** Report vulnerabilities to [security@10x-software.org](mailto:security@10x-software.org)
- **Discord:** [Join the 10x Community](https://discord.gg/m7AQSXfFwf)
