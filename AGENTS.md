## py10x-universe – Guide for AI Agents

This file is a **meta-guide** for tools and AI agents working in this repo.  
It points to canonical docs and records only the minimal, project-specific rules that agents must obey.

---

## 1. Where canonical knowledge lives

- **High-level overview**: see `README.md`.
- **Installation / environment details**: see `INSTALLATION.md`.
- **Concepts, traitables, getters/setters, storage, execution modes**: see `GETTING_STARTED.md`.
- **Contribution workflow, code style, test layout**: see `CONTRIBUTING.md`.
- **Security, changelog, community**: see `SECURITY.md`, `CHANGELOG.md`, `CODE_OF_CONDUCT.md`.
- **Low-level traitable implementation details**: see `core_10x/traitable.py` and existing tests in `core_10x/unit_tests/`.

Agents should **link to and rely on those files**, not duplicate them here.

---

## 2. Environment & tooling rules for agents

- **Use UV and the project venv**
  - Assume development happens via `uv` and a local `.venv`.
  - When suggesting or running commands, prefer:
    - `uv sync --all-extras` for dependency setup.
    - `uv run ...` for Python tooling (`pytest`, `ruff`, etc.).

- **Respect C++ / cxx10x backend**
  - Treat `core-10x-i` / `infra-10x-i` (from `cxx10x`) as **opaque C++ backends**.
  - Do **not** try to reimplement or bypass them in Python; use the public Python APIs.

- **MongoDB & UI assumptions**
  - Some tests require a local passwordless MongoDB on port 27017.
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
  - Do not change the meaning of ID vs ID_LIKE vs regular vs runtime traits; follow the patterns and explanations in `GETTING_STARTED.md` (“Core Concepts”, “Object Identification System”).

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
    - `uv run pytest` (or narrower paths) for tests.
    - `uv run ruff check .` and `uv run ruff format .` for linting/formatting.

When adding new functionality, agents should **add or update tests** in the appropriate suite following nearby examples, rather than inventing new test patterns.

---

## 5. Default agent behavior in this repo

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


