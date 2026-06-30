## `py10x-core` – Guide for AI Agents

This file is a **meta-guide** for tools and AI agents working in this repo.  
It points to canonical docs and records only the minimal, project-specific rules that agents must obey.

---

## 1. Where canonical knowledge lives

- **High-level overview**: see `README.md`.
- **Installation / environment details**: see `INSTALLATION.md`.
- **Concepts, traitables, getters/setters, storage, execution modes**: see `GETTING_STARTED.md`.
- **Contribution workflow, code style, test layout**: see `CONTRIBUTING.md`.
- **Security, changelog, community**: see `SECURITY.md`, `CHANGELOG.md`, `CODE_OF_CONDUCT.md`.
- **Release engineering & dev tooling** (`uv-sync`, `xx-promote`, `constraints.txt`, CI gates): see `dev_10x/README.md`.
- **Low-level traitable implementation details**: see `core_10x/traitable.py` and existing tests in `core_10x/unit_tests/`.
- **C++ backend source (cxx10x)**: lives in the sibling package `../cxx10x/` (e.g. `../cxx10x/core_10x/btraitable.{h,cpp}`, `../cxx10x/core_10x/core_10x.cpp` for pybind11 bindings). When a Python method's body is just a thin wrapper or its docstring/comment says it is provided "from c++" (e.g. the comment block in `core_10x/traitable.py` around `get_value` / `set_value` / `set_values`), consult these files to confirm the actual signature and surface area exposed to Python.

Agents should **link to and rely on those files**, not duplicate them here.

---

## 2. Environment & tooling rules for agents

- **Use UV and the project venv**
  - Assume development happens via `uv` and a local `.venv`.
  - When suggesting or running commands, prefer:
    - `uv-sync py10x-core-dev --all-extras` for dependency setup (see `dev_10x/README.md`).
    - `uv-run pytest …` / `uv run …` for Python tooling after the venv is prepared.

- **Respect C++ / cxx10x backend**
  - Treat the C++ backends (from `cxx10x`) as **opaque** — do not reimplement or bypass them in Python; use the public Python APIs.
  - Do **not** try to reimplement or bypass them in Python; use the public Python APIs.
  - The C++ source lives in the sibling package at `../cxx10x/` (sibling to this repo's checkout). Read it (don't modify it from this repo) when you need to verify what is actually exposed to Python — in particular `../cxx10x/core_10x/btraitable.h` for the `BTraitable` API surface and `../cxx10x/core_10x/core_10x.cpp` for the pybind11 bindings that determine which methods are visible from Python.

- **Traitable Store & UI assumptions**
  - `core_10x` tests use the in-process Traitable Store. `infra_10x` tests use the MongoDB-backed store (where it is implemented) and require a local passwordless MongoDB on port 27017.
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

**Canonical documentation:** `dev_10x/README.md` (pin model, `xx-promote`, `uv-sync`, `constraints.txt`, CI). Read it before changing anything under `dev_10x/` or release workflows. Do not duplicate that content here.

Rules agents must **not** violate when touching this area:

- **Never `==`-pin *third-party* `[project.dependencies]`** in published metadata — use ranges; reproducibility is `constraints.txt` + `-c`, not exact pins on third-party deps. **Carve-out:** the co-released first-party family *is* `==`-pinned on `pre`/`prod` (core → siblings, exact coordinated version) — this is the external rc coordination guarantee; see `dev_10x/README.md` "Pin model" and `dev_10x/docs/rc-branch-promotion.md`. `main` still carries dev ranges, never `==`.
- **Keep `dev_10x/xx_ci.py` kernel-free** — no `core_10x` imports; tag resolution runs before siblings install.
- **Keep `uv-sync` pip-install based** — do not reintroduce transient `[tool.uv.sources]` edits to `pyproject.toml` (dirty tree breaks setuptools-scm).
- **Apply `-c constraints.txt` on every pip install** path (`uv_sync.py`, CI workflows). After adding/changing deps, run `xx-constraints compile` in `py10x-core-dev` mode and commit `constraints.txt`.
- **Sibling paths** live in `[tool.dev_10x.siblings]` only — `uv_sync.py`, `xx_promote.py`, and `constraints.py` read from there; keep them in sync.
- **Version ordering:** always `packaging.version.Version` (`max`), never `git --sort=-v:refname` / `sort -V`.
- **`local == remote` invariant + atomic recovery for `xx-promote`:** a real run starts synced (`GitHelpers.require_synced`: clean tree + `main`/managed-tags == `origin`, fetch-first) and, with `--push`, finishes synced by pushing **each repo's bundled refs in one atomic push** (`git push --atomic`, all-or-nothing) plus each **publish trigger isolated** (its own push, so the tag-create webhook fires). Crash recovery is **`xx-promote resync`** (force local managed refs back to `origin`) + idempotent re-run — **not** in-place reconcile (retired; atomic pushes make its repair states unreachable). Don't bypass the precondition, split a repo's bundled push into non-atomic pushes, or push refs outside the declared `Step.tags_to_push` / `Step.isolated_tags_to_push`. See `dev_10x/README.md` "local == remote invariant + atomic recovery".
- **Publish is trigger-tag-driven; `main` carries `.dev` setuptools-scm markers.** Workflows fire only on the isolated `pre/`/`prod/` **publish-trigger** tags — *not* the version tags or `.dev` markers, which ride the webhook-free bundled push. Don't point a publish workflow at version tags, merge a trigger's create with its stale deletes into one push, or drop `main`'s `.dev` markers (they hold setuptools-scm above the latest release so an editable install isn't downgraded to a published wheel). A crash that landed state but not triggers recovers with `resync` then `xx-promote pre|prod --publish --push`. See `dev_10x/README.md` "xx-promote" / "CI release gates".
- **setuptools-scm traps:** dirty `pyproject.toml` → wrong dev version; shallow checkout → `0.1.dev1+g…`; CI needs `fetch-depth: 0` (cxx wheels, sibling resolution) and `fetch-tags: true` (`build.yml`, to find the version tag co-located with the trigger commit).
- **CI:** tag triggers exclude `*_yanked`; `uv pip install --all-extras` needs `-e . --all-extras --requirements pyproject.toml`.
- **Tests** for promotion: pure helpers/pin-form guards `dev_10x/unit_tests/test_xx_utils.py`; pure batch planner `test_xx_plan.py`; CLI routing `test_xx_promote.py`; real-git execution (cut/promote/yank, resync recovery, atomic bare-remote push) `test_xx_promote_e2e.py`; external-tool assumption guards `test_xx_tooling_guards.py`.

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

Standard commands per `CONTRIBUTING.md` and section 4 above:

- **Tests:** `uv run pytest` (all), or scope to a package: `uv run pytest core_10x/unit_tests/`
- **Lint:** `uv run ruff check .`
- **Format:** `uv run ruff format .`
- **Build:** `uv build`

### Non-obvious caveats

- MongoDB must run as a **replica set** (`--replSet rs0`), not standalone — the infra layer uses transactions.
- The Docker socket permissions may need fixing after daemon restart: `sudo chmod 666 /var/run/docker.sock`.
- The Docker storage driver is set to `fuse-overlayfs` and iptables uses `iptables-legacy` — these are required for nested container environments.
- `uv` is installed at `~/.local/bin/uv`; ensure `$HOME/.local/bin` is on `PATH`.
