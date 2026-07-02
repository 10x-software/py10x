## `py10x-core` – Guide for AI Agents

This file is a **meta-guide** for tools and AI agents working in this repo.  
It points to canonical docs and records only the minimal, project-specific rules that agents must obey.

---

## 1. Where canonical knowledge lives

- **High-level overview**: see [`README.md`](README.md).
- **Installation / environment details**: see [`INSTALLATION.md`](INSTALLATION.md).
- **Concepts, traitables, getters/setters, storage, execution modes**: see [`GETTING_STARTED.md`](GETTING_STARTED.md).
- **Contribution workflow, code style, test layout**: see [`CONTRIBUTING.md`](CONTRIBUTING.md).
- **Security, changelog, community**: see `SECURITY.md`, `CHANGELOG.md`, `CODE_OF_CONDUCT.md`.
- **Release engineering & dev tooling** (`uv-sync`, `xx-promote`, `constraints.txt`, CI gates): see [`dev_10x/README.md`](dev_10x/README.md). Agent guardrails: §7 below.
- **Low-level traitable implementation details**: see `core_10x/traitable.py` and existing tests in `core_10x/unit_tests/`.
- **C++ backend source (cxx10x)**: lives in the sibling package `../cxx10x/` (e.g. `../cxx10x/core_10x/btraitable.{h,cpp}`, `../cxx10x/core_10x/core_10x.cpp` for pybind11 bindings). When a Python method's body is just a thin wrapper or its docstring/comment says it is provided "from c++" (e.g. the comment block in `core_10x/traitable.py` around `get_value` / `set_value` / `set_values`), consult these files to confirm the actual signature and surface area exposed to Python.

Agents should **link to and rely on those files**, not duplicate them here.

---

## 2. Environment & tooling rules for agents

- **Use UV and the project venv**
  - Assume development happens via `uv` and a local `.venv`.
  - When suggesting or running commands, prefer:
    - `uv-sync py10x-core-dev --all-extras` for dependency setup (see `dev_10x/README.md`).
    - `uv-run --no-sync pytest …` / `uv --no-sync run …` for Python tooling after the venv is prepared.

- **Respect C++ / cxx10x backend**
  - Treat the C++ backends (from `cxx10x`) as **opaque** — do not reimplement or bypass them in Python; use the public Python APIs.
  - The C++ source lives in the sibling package at `../cxx10x/` (sibling to this repo's checkout). Read it (don't modify it from this repo) when you need to verify what is actually exposed to Python — in particular `../cxx10x/core_10x/btraitable.h` for the `BTraitable` API surface and `../cxx10x/core_10x/core_10x.cpp` for the pybind11 bindings that determine which methods are visible from Python.

- **Traitable Store & UI assumptions**
  - `infra_10x` tests need MongoDB — see `INSTALLATION.md` § Optional Database Dependencies.
  - UI work should assume Rio/Qt backends as configured in `INSTALLATION.md` / `pyproject.toml`.

For any environment ambiguity, favor the patterns and instructions in `INSTALLATION.md` and `CONTRIBUTING.md`.

---

## 3. Traitable invariants agents must preserve

Most important invariants are around `core_10x.traitable.Traitable` and are documented in `GETTING_STARTED.md` and `core_10x/traitable.py`.  
Agents must **not** violate the following:

- **Construction & initialization**
  - **Never override `__init__`** on subclasses of `Traitable`; use `__post_init__` instead.
  - Only use `_replace=True` in constructors when you intentionally want to update non-ID traits of an existing entity with the same ID.

- **Trait definitions**
  - Always provide a **type annotation** for each trait, and use `T(...)` / `RT(...)` / `M(...)` as in the existing code.
  - Do not change the meaning of ID vs ID_LIKE vs regular vs runtime traits; follow `GETTING_STARTED.md` ([Core Concepts](GETTING_STARTED.md#core-concepts), [Object Identification System](GETTING_STARTED.md#object-identification-system)).

- **Getters / setters / converters**
  - Follow the existing naming contracts (`*_get`, `*_set`, `*_from_str`, `*_from_any_xstr`).
  - Keep getters side-effect free; put validation / cross-field updates into setters.

- **Storage & identity**
  - Maintain the shared-by-ID semantics: instances with the same ID share trait values.
  - Respect storage contexts (`CACHE_ONLY`, `MongoStore.instance(...)`) and do not introduce ad-hoc persistence mechanisms.

Before changing anything under `core_10x/traitable.py` or traitable-heavy code, agents should:
- Read the relevant sections of `GETTING_STARTED.md`.
- Scan the corresponding tests in `core_10x/unit_tests/` to mirror existing patterns.

---

## 4. Testing & layout expectations

- **Test placement**
  - Core logic tests belong in `core_10x/unit_tests/`.
  - UI tests belong in `ui_10x/unit_tests/` or backend-specific test folders.
  - Infra/storage tests belong in `infra_10x/unit_tests/`.

- **How to run tests / lints**
  - Prefer:
    - `uv run --no-sync pytest` (or narrower paths) for tests.
    - `uv run --no-sync ruff check .` and `uv run --no-sync ruff format .` for linting/formatting.

When adding new functionality, agents should **add or update tests** in the appropriate suite following nearby examples, rather than inventing new test patterns.

---

## 5. Language & style

- **Use American English spelling** throughout all code, comments, docstrings, and documentation.
  - ✓ `serializable`, `behavior`, `color`, `initialize`, `recognize`, `analyze`
  - ✗ `serialisable`, `behaviour`, `colour`, `initialise`, `recognise`, `analyse`

---

## 6. Default agent behavior in this repo

- **Prefer existing patterns over new abstractions**
  - When in doubt, copy the style and structure from nearby code and tests instead of inventing a new mini-framework.

- **Minimize duplication**
  - If some behavior is already described in `README.md`, `GETTING_STARTED.md`, or tests, link or reference it rather than restating it.

- **Be conservative with Traitable changes**
  - Any changes in this package are potentially high impact.
  - Such changes should:
    - Be as small/local as possible.
    - Include focused tests.
    - Keep public semantics consistent with existing docs unless the change is explicitly a breaking redesign.

---

## 7. Release engineering — agent guardrails

**Canonical documentation:** [`dev_10x/README.md`](dev_10x/README.md). Read it before changing anything under `dev_10x/` or release workflows.

Rules agents must **not** violate:

- **Third-party deps:** never `==`-pin `[project.dependencies]` in published metadata — use ranges + [`constraints.txt`](dev_10x/README.md#constraintstxt--reproducibility). First-party siblings are `==`-pinned on `pre`/`prod` only — see [Pin model](dev_10x/README.md#pin-model-three-places).
- **`xx_ci.py` kernel-free** — no `core_10x` imports before siblings install.
- **`uv-sync` pip-install based** — no transient `[tool.uv.sources]` edits to `pyproject.toml`.
- **`-c constraints.txt`** on every pip install; run `xx-constraints compile` after dep changes.
- **Sibling paths** in `[tool.dev_10x.siblings]` only — keep `uv_sync.py`, `xx_promote.py`, `constraints.py` in sync.
- **Version ordering:** `packaging.version.Version` (`max`), never `git --sort=-v:refname` / `sort -V`.
- **`xx-promote` sync + recovery:** start/finish with local == `origin`; atomic `git push --atomic` per repo; isolated publish-trigger pushes — see [xx-promote](dev_10x/README.md#xx-promote--release-promotion). Recovery: `resync` + idempotent re-run, not in-place reconcile.
- **Publish triggers only** on `pre/`/`prod/` tags — not version tags or `.dev` markers on `main` — see [CI release gates](dev_10x/README.md#ci-release-gates).
- **setuptools-scm:** dirty `pyproject.toml` or shallow checkout breaks versions; CI needs `fetch-depth: 0` and `fetch-tags: true`.
- **CI install:** `uv pip install -e . --all-extras --requirements pyproject.toml`; tag triggers exclude `*_yanked`.
- **Promotion tests:** `test_xx_utils.py`, `test_xx_plan.py`, `test_xx_promote.py`, `test_xx_promote_e2e.py`, `test_xx_tooling_guards.py`.

## Cursor Cloud specific instructions

### Services overview

| Service | Purpose | How to start |
|---------|---------|-------------|
| MongoDB 8 (replica set) | Required for `infra_10x` tests | `docker start mongo-rs` (container pre-exists in snapshot) |
| Docker daemon | Hosts MongoDB container | `sudo dockerd &>/tmp/dockerd.log &` |
| Playwright/Chromium | Required for `ui_10x/rio` browser-based tests | Pre-installed; no startup needed |

### Starting services before running tests

The Docker daemon and MongoDB container are already configured but **not auto-started**. Before running tests that touch `infra_10x`:

```bash
sudo dockerd &>/tmp/dockerd.log &
sleep 3
docker start mongo-rs
```

Wait for MongoDB to be writable (the replica set is already initiated):

```bash
docker exec mongo-rs mongosh --quiet --eval "db.hello().isWritablePrimary"
# Should print: true
```

`core_10x`, `xx_common`, and `ui_10x` tests do **not** require MongoDB.

### Running tests, lint, and build

See [CONTRIBUTING.md](CONTRIBUTING.md#development-workflow) (`uv run --no-sync pytest`, `uv run --no-sync ruff`, `uv --no-sync build`).

### Non-obvious caveats

- MongoDB must run as a **replica set** (`--replSet rs0`), not standalone — see [INSTALLATION.md](INSTALLATION.md#optional-database-dependencies).
- The Docker socket permissions may need fixing after daemon restart: `sudo chmod 666 /var/run/docker.sock`.
- The Docker storage driver is set to `fuse-overlayfs` and iptables uses `iptables-legacy` — these are required for nested container environments.
- `uv` is installed at `~/.local/bin/uv`; ensure `$HOME/.local/bin` is on `PATH`.
