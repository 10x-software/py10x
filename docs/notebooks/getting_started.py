# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = [
#     "marimo",
#     "py10x-core>=0.3.1",
# ]
# ///
"""Interactive companion to README.md and GETTING_STARTED.md.

Run locally:
    uvx marimo edit --sandbox docs/notebooks/getting_started.py

Host on molab (free): push this file, then on https://molab.new use
"New → From GitHub" and paste the raw GitHub URL. Prefer a *server*
preview — native wheels (py10x-kernel / py10x-infra) are not WASM-compatible.
"""

import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")

with app.setup:
    import marimo as mo
    from datetime import date

    from core_10x.exec_control import CACHE_ONLY, GRAPH_ON
    from core_10x.traitable import RT, T, Traitable


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # py10x-core — interactive getting started

    This is a [marimo](https://marimo.io) notebook: reactive Python cells that
    re-run when their inputs change (not a Jupyter notebook). It supplements the
    [README](https://github.com/10x-software/py10x/blob/main/README.md)
    and [Getting Started](https://github.com/10x-software/py10x/blob/main/GETTING_STARTED.md)
    guides and runs entirely in memory (`CACHE_ONLY`) — no Mongo, Postgres, or UI backend.

    **Running in the browser:** open this file on [molab](https://docs.marimo.io/guides/molab/)
    (marimo’s free hosted workspace). Create a free account to execute cells, and
    start a **server** session — native wheels (`py10x-kernel` / `py10x-infra`) are
    not WebAssembly-compatible.

    **Four laws, in practice:** identity · dependency · persistence · presentation.
    Here we exercise the first two interactively; persistence and derived UI are
    documented in the guides above.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 1. Runtime traitables — no storage context

    If every trait is runtime (`RT()` or a bare annotation), construction works
    with no store. Computed traits use `*_get` methods and recompute when inputs change.
    """)
    return


@app.class_definition
class Calculator(Traitable):
    x: int
    y: int
    sum: int
    product: int

    def sum_get(self) -> int:
        return self.x + self.y

    def product_get(self) -> int:
        return self.x * self.y


@app.cell(hide_code=True)
def _():
    x_slider = mo.ui.slider(0, 20, value=5, label="x", show_value=True)
    y_slider = mo.ui.slider(0, 20, value=3, label="y", show_value=True)
    mo.hstack([x_slider, y_slider], justify="start")
    return x_slider, y_slider


@app.cell
def _(x_slider, y_slider):
    calc = Calculator(x=x_slider.value, y=y_slider.value)
    mo.md(
        f"""
    | trait | value |
    |-------|------:|
    | `x` | `{calc.x}` |
    | `y` | `{calc.y}` |
    | `sum` | **`{calc.sum}`** |
    | `product`| **`{calc.product}`** |

    Move the sliders — getters recompute on each access.
    """
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 2. Identity and dependency — the README nine-liner

    - `T(T.ID)` marks an **identity** trait: same ID → shared trait values.
    - `T(...)` is a **persistent** trait (stored when a real Traitable Store is active).
    - `RT()` is **runtime-only** (never stored).
    - With `GRAPH_ON()`, changing an input invalidates dependents so the next read recomputes.
    """)
    return


@app.class_definition
class Developer(Traitable):
    handle: str = T(T.ID)
    coffee_cups: int = T(default=0)
    energy: int = RT()

    def energy_get(self) -> int:
        return self.coffee_cups * 20


@app.cell(hide_code=True)
def _():
    handle = mo.ui.text(value="ghost", label="handle (ID trait)")
    cups = mo.ui.slider(0, 12, value=5, label="coffee_cups", show_value=True)
    mo.hstack([handle, cups], justify="start")
    return cups, handle


@app.cell
def _(cups, handle):
    with CACHE_ONLY(), GRAPH_ON():
        dev = Developer(handle=handle.value or "ghost")
        dev.coffee_cups = cups.value
        energy = dev.energy
        # Same identity → shares trait values with `dev`
        twin = Developer(handle=handle.value or "ghost")
        twin_energy = twin.energy
        twin_cups = twin.coffee_cups

    mo.md(
        f"""
    ```text
    dev  = Developer(handle={handle.value!r})
    dev.coffee_cups = {cups.value}
    dev.energy  →  {energy}

    twin = Developer(handle={handle.value!r})   # same ID
    twin.coffee_cups  →  {twin_cups}   # shared
    twin.energy       →  {twin_energy}
    ```

    `dev is twin` is **False** (construction always returns a new instance), but
    trait values are shared by ID — that is the identity law.
    """
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 3. Stored ID traits need a storage context

    Endogenous traitables with regular (`T()`) traits require a store context even
    when you are only playing in memory. `CACHE_ONLY()` is the in-process stand-in;
    swap it for `Traitable.store_from_uri(...)` when you want Mongo / Postgres / DuckDB.
    """)
    return


@app.class_definition
class Person(Traitable):
    first_name: str = T(T.ID)
    last_name: str = T(T.ID)
    dob: date = T()
    age: int
    full_name: str

    def age_get(self) -> int:
        if not self.dob:
            return 0
        today = date.today()
        years = today.year - self.dob.year
        if (today.month, today.day) < (self.dob.month, self.dob.day):
            years -= 1
        return years

    def full_name_get(self) -> str:
        return f"{self.first_name} {self.last_name}"


@app.cell(hide_code=True)
def _():
    first = mo.ui.text(value="Alice", label="first_name")
    last = mo.ui.text(value="Smith", label="last_name")
    year = mo.ui.number(1950, 2020, value=1990, label="birth year")
    mo.hstack([first, last, year], justify="start")
    return first, last, year


@app.cell
def _(first, last, year):
    with CACHE_ONLY():
        person = Person(first_name=first.value or "Alice", last_name=last.value or "Smith")
        person.dob = date(int(year.value), 5, 15)
        # Resolve again by ID — shares traits with `person`
        again = Person(first_name=first.value or "Alice", last_name=last.value or "Smith")

    mo.md(
        f"""
    **{person.full_name}** · DOB `{person.dob}` · age **{person.age}**

    Second construction with the same ID traits sees the same stored traits:
    `again.dob == person.dob` → `{again.dob == person.dob}` · `again.age` → `{again.age}`.
    """
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Next steps

    | Topic | Where |
    |-------|--------|
    | Persistence, versioning, queries | [Traitable Store](https://github.com/10x-software/py10x/blob/main/GETTING_STARTED.md#traitable-store) |
    | Credential vault | [Vault](https://github.com/10x-software/py10x/blob/main/GETTING_STARTED.md#vault-and-credential-management) |
    | Derived Qt / Rio UI | [UI Framework Integration](https://github.com/10x-software/py10x/blob/main/GETTING_STARTED.md#ui-framework-integration) |
    | Install | [INSTALLATION.md](https://github.com/10x-software/py10x/blob/main/INSTALLATION.md) |
    | Finance subject domain | [xx_fin/README.md](https://github.com/10x-software/py10x/blob/main/xx_fin/README.md) |

    ### Run this notebook

    ```bash
    # local (sandboxed deps from the PEP 723 header)
    uvx marimo edit --sandbox docs/notebooks/getting_started.py
    ```

    ### Host on molab (free)

    [molab](https://docs.marimo.io/guides/molab/) is marimo’s free cloud workspace.
    Viewers can open the GitHub-mirrored link below; a free account is required
    to run cells. Use a **server** session (not WebAssembly) — `py10x-core` ships
    native wheels.

    1. Push this file to GitHub.
    2. Open [molab.new](https://molab.new) → **New** → paste the GitHub file URL (synced notebook), or share the open-in-molab badge.
    3. Sign in / create a free account when prompted to execute.
    """)
    return


if __name__ == "__main__":
    app.run()
