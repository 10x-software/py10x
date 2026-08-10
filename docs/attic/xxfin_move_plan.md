# Move `xxfin` / `cxxfin` → `py10x-fin-base` (extract plan)

> **Archived** (2026-08-10). Migration complete — live tree is `py10x/xx_fin/`. Kept under
> `docs/attic/` for design history only; do not treat as an active todo list.

**Status:** Relocate + domain hard-cut done. Live tree is `py10x/xx_fin/`; domain
depends on editable `../py10x` (+ PyPI kernel/infra). Co-release train on PyPI through
**fin-base/cxx `0.1.0rc5`**, core **`0.2.3rc51`** (and later `.dev` / rc bumps).  
**Last updated:** 2026-08-10  

Extract the financial base into published packages, then relocate the already-packaged
`xx_fin/` tree into the py10x monorepo as the first real **downstream** of `py10x-core`.

An earlier idea to also extract `xx_common` as `py10x-common-domain` was **cancelled**.

Day-to-day domain DX: `[tool.uv.sources]` editables for `../py10x`,
`../py10x/xx_fin`, `../py10x/xx_fin/cxxfin`. Python changes visible after merge to
py10x `main` + `git pull --no-rebase origin main`. Work on `sandbox/<who>`; main is
protected. Kernel/infra stay on PyPI (optional local `-e ../cxx10x/…`).

---

## Goals

| Goal | Detail |
|------|--------|
| **Product dist** | PyPI **`py10x-fin-base`** (only consumer-facing install name) |
| **Impl dist** | PyPI **`py10x-fin-base-cxx`** (not separately supported; pulled as a dependency) |
| **Imports** | **`xxfin`** + **`cxxfin`** (unchanged) |
| **Layout** | `py10x/xx_fin/{xxfin,cxxfin}` (relocated; domain attic keeps a historical copy) |
| **Publish shape** | **C**: two build artifacts, one product — `py10x-fin-base` depends on `py10x-fin-base-cxx` |
| **Release (after relocate)** | First real **downstream** of `py10x-core` via `[tool.dev_10x.downstream]` |
| **Hard cut** | Domain drops local workspace `xx_fin/` once it depends on published (or editable) dists from py10x |

### Related work already decided / done

| Item | Status |
|------|--------|
| Rename `xx_common` → **`xxcommon`** inside `py10x-core` | Done (stays in the `py10x-core` wheel) |
| Separate PyPI package for common | **Cancelled** |
| Nested packaging root for common | **Not doing** |
| **Phase 0:** packageize + co-locate under `xx-fin-domain/xx_fin/` | **Done** (`4205538`) |

```python
from xxcommon.rdate import RDate
from xxfin.ccy import …          # py10x-fin-base (published or editable ../py10x/xx_fin)
```

Consumers install **`py10x-fin-base` only** (never depend on `py10x-fin-base-cxx` directly).

---

## Phases

| Phase | Where | Status |
|-------|--------|--------|
| **0** | `xx-fin-domain` | **Done** — workspace packages, layout, boundary cleanup |
| **1** | `xx-fin-domain` | **Done** — publish rehearsal; first PyPI rc from domain |
| **2** | `py10x` | **Done** — `[tool.dev_10x.downstream]` promote tooling + live `./xx_fin` entry |
| **3** | `py10x` + domain | **Done** — tree at `py10x/xx_fin/`; domain attic + editable/PyPI hard-cut |

Migration complete for relocate / hard-cut / CI downstream validation / consumer docs.

---

## Phase 0 (done) — packageize in `xx-fin-domain`

Landed as **`4205538`** — *move xxfin/cxxfin into xx_fin in prep to oss*.

### Layout (current)

```text
xx-fin-domain/
  xx_fin/
    pyproject.toml                 # name = "py10x-fin-base"
    README.md
    xxfin/                         # import xxfin
    cxxfin/                        # dist py10x-fin-base-cxx; import cxxfin
      pyproject.toml
  pyproject.toml                   # xx-fin-domain; depends on py10x-fin-base only
  xxfin_commod/ …
  xxfin_positions/ …
  xxfin_testing/ …
```

### Packaging facts

| Dist | Path | Import | Notes |
|------|------|--------|--------|
| `py10x-fin-base` | `xx_fin/` | `xxfin` | hatch + hatch-vcs; tags `py10x-fin-base-v*` |
| `py10x-fin-base-cxx` | `xx_fin/cxxfin/` | `cxxfin` | scikit-build; tags `py10x-fin-base-cxx-v*`; cibuildwheel workflow retargeted |
| `xx-fin-domain` | repo root | commod / positions / testing | hatch packages no longer include `xxfin` |

- Workspace: `members = ["xx_fin", "xx_fin/cxxfin"]`
- Root depends on **`py10x-fin-base`** only; cxx is transitive
- Fin-base deps include `py10x-core`, `py10x-fin-base-cxx`, `quantlib-python`, optional `aadc`, extra `bbg`
- Boundary: `mkt_risk_proto` → `xxfin_commod`; positions store associations split out of fin-base helpers

### Still open from Phase 0

- [x] Track `xxfin_positions/dev_data_helpers/` on domain `main` (positions store associations)

---

## Target dependency graph (after relocate)

```text
py10x-kernel ──┐
py10x-infra  ──┼──► py10x-core
               │      (ships core_10x, ui_10x, infra_10x, dev_10x, xxcommon)
               │         │
               │         └── does NOT depend on py10x-fin-base
               │
               └──► py10x-fin-base        (import xxfin)
                      └── py10x-fin-base-cxx   (import cxxfin; impl wheel)
                              │
                              ├── xx-fin-domain (commod / positions / apps)
                              └── other consumers
```

**Fin-base does not need a separate pin on `xxcommon`:** it depends on **`py10x-core`**, which ships `xxcommon`.

Whether promote registers one downstream (`py10x-fin-base`) or also tracks `py10x-fin-base-cxx`
is decided in Phase 1/2; product rule stays **one consumer-facing name**.

---

## Layout after relocate to py10x

Same tree as domain Phase 0 — path change only:

```text
py10x/
  xx_fin/
    pyproject.toml                 # py10x-fin-base
    README.md
    xxfin/
    cxxfin/                        # py10x-fin-base-cxx
      pyproject.toml
```

---

## Phase 1 (done) — publish story in domain

Landed as a single merged workflow — **`.github/workflows/finbase_wheel.yml`**, tag `py10x-fin-base-v*`
(the earlier separate `cxxfin_wheels.yml` / `py10x-fin-base-cxx-v*` tag was folded in; both packages
are tagged/built/published together from one tag).

1. ~~Tag / build `py10x-fin-base-cxx`~~ — done as part of the merged workflow, not a separate tag.
2. **Tag / build `py10x-fin-base`** — done; pure-Python hatch wheel, metadata depends on cxx + core.
3. **Coordinate versions** — done via a shared `git describe` tag pattern (both packages resolve the
   same version from one tag) plus an exact `py10x-fin-base-cxx==<version>` pin, hand-committed in
   `xx_fin/pyproject.toml` before tagging and only *validated* (not edited) by CI — editing it
   post-checkout left the tree dirty and produced an unpublishable `+dirty` version. Later
   automated via `xx-promote` co-release pins (`{name}-cxx==` on fin-base release commits).
4. **Clean venv smoke** — done, and automated: a `smoke_test` CI job installs straight from that
   run's build artifacts (not the index) across all 3 OSes and runs `import xxfin; import cxxfin`,
   gating `publish` on it passing — not a manual post-hoc step. Post-relocate workflow also waits
   for pip-visible sibling releases before smoke (`wait_finbase_pypi_deps`).
5. Skipped TestPyPI — published directly to real PyPI. First domain rc was `v0.1.0rc1`; py10x
   co-release train has continued (e.g. `v0.1.0rc5`).

---

## Phase 2 — Promote: `[tool.dev_10x.downstream]`

Fin-base is a **downstream** of core (depends on core; core does not depend on it). Do **not**
put it under `[tool.dev_10x.siblings]` (siblings are packages core depends on: kernel/infra).

### Config (root `pyproject.toml`)

```toml
[tool.dev_10x.siblings]
py10x-kernel = { path = "../cxx10x/core_10x" }
py10x-infra  = { path = "../cxx10x/infra_10x" }

[tool.dev_10x.downstream]
py10x-fin-base = { path = "./xx_fin" }
# default tag_prefix = "py10x-fin-base-v"
# py10x-fin-base-cxx: either a second downstream entry or owned as a build unit of fin-base
```

Registry should be a **map of N** packages so more downstreams can be added later without rewiring.

### Why not a sibling

If fin-base were a sibling, promote would:

1. Make **core publish a dependency on `py10x-fin-base`**.
2. Force a **core re-cut** whenever fin-base changes (`pin_lag`).
3. Only write a **dev-only `test` group** reverse pin (not a published consumer pin).
4. Risk **`uv-sync` treating it as C++** (worse once `cxxfin` lives under `xx_fin/`).

### Re-cut rules

1. **Siblings** — re-cut iff own footprint changed.
2. **Core** — re-cut iff own footprint **or** sibling pin lag (siblings only). `xxcommon/` changes count as **core**.
3. **Each downstream** (fin-base) — re-cut iff own footprint **or** published `py10x-core` pin lags the batch’s coordinated core version.

| Scenario | Result |
|----------|--------|
| Only `xx_fin/**` changes | Cut fin-base (+ cxx as needed); core skipped (footprint excludes `xx_fin/`) |
| Core re-cut | Fin-base re-cuts if its core pin is stale |

### Pin forms (fin-base → core)

| Place | Fin-base’s `py10x-core` pin | Core → fin-base |
|-------|----------------------------|-----------------|
| `pre` / `prod` tag commit | `==` coordinated core | **none** published |
| `main` after `pre` | rc-window | unpublished `dependency-groups.test` `py10x-fin-base>=…` |
| `main` after `prod` | post-final window | same test-group refresh |

Reuse `PyProjectHelpers.write_forward_pins` on `xx_fin/pyproject.toml` (must already list `py10x-core` in `[project.dependencies]`). Downstream does **not** carry a test-group pin to core; core’s unpublished test group tracks the downstream.

### Footprint (same-repo multi-package)

| Change under | Core | fin-base |
|--------------|------|----------|
| `xxcommon/**`, `core_10x/**`, … | trips | shared root may trip |
| `xx_fin/**` | **excluded** | trips |

### Tags / branches / publish (after relocate)

| Item | Fin-base | Fin-base-cxx |
|------|----------|--------------|
| Tag prefix | `py10x-fin-base-v` | `py10x-fin-base-cxx-v` |
| Branches | `pre-py10x-fin-base`, `prod-py10x-fin-base` (flat; cannot use `pre/{name}` — core already owns bare `pre` in the same repo) | co-released on fin-base train (no separate branch) |
| Publish triggers | `pre/prod/py10x-fin-base-v*` (tags; `refs/tags/` OK alongside branch `pre`) | folded into fin-base train |

Prefer a **parameterized** publish workflow template so additional downstreams are cheap.

### Yank

| Yank target | Effect |
|-------------|--------|
| Sibling | existing core main forward-pin refresh |
| Core | also refresh **each** downstream’s main `py10x-core` pin + core test-group |
| Downstream | roll its branch/tags + refresh **core’s test-group** pin only (no published core deps) |

### `uv_sync` / constraints / `xx_ci`

| Module | Behavior |
|--------|----------|
| `uv_sync` | Default: siblings + core. Downstream install **opt-in** (`--with-downstream py10x-fin-base` or equivalent). |
| `constraints` | Compile includes `xx_fin/pyproject.toml` (+ cxx pyproject); first-party names. |
| `xx_ci` | Sibling pin-wait unchanged; no wait for downstream. |

### Tooling touch list

| File | Change |
|------|--------|
| `xx_promote.py` `packages_get` | Load `[tool.dev_10x.downstream]`; keep core last |
| `xx_plan.py` | `is_downstream`; core forward targets = siblings only; per-downstream pin lag |
| Epilogues / yank | Downstream main pins; yank core refreshes all downstreams |
| `uv_sync.py` | Opt-in downstream install (pure Python + optional native wheel) |
| `constraints.py` | First-party + compile inputs |
| `dev_10x/README.md`, `AGENTS.md` §7 | Document the third role (downstream) |

---

## Phase 3 — Relocate + domain hard-cut (**done**)

1. ~~Move `xx-fin-domain/xx_fin/` → `py10x/xx_fin/`~~ — live under py10x; domain copy in `attic/xx_fin/`.
2. ~~Register downstream; publish workflows on py10x~~ — `[tool.dev_10x.downstream]`,
   `finbase_wheel.yml`. CI: same job asserts isolation then `--with-downstream` + `xx_fin/` tests.
3. ~~Domain hard-cut~~ — depends on `py10x-fin-base`; no local workspace member.
4. Imports remain `xxfin` / `cxxfin`.

Domain normal mode (`BUILD-NOTES.txt` + `[tool.uv.sources]`):

```bash
# requires ../py10x checkout
uv sync --upgrade
# editables: py10x-core, py10x-fin-base, py10x-fin-base-cxx from ../py10x
# kernel/infra: PyPI (optional: uv pip install -e ../cxx10x/…)
```

---

## Test isolation (after relocate)

Enforce “core does not depend on fin-base” with **sequential steps in the same CI job**
(`.github/actions/ci-test-suite`), not only packaging metadata.

| Step | Env | Runs | Must not be importable |
|------|-----|------|------------------------|
| **Core** | siblings + `py10x-core` (no `--with-downstream`) | core / ui / infra / dev + **xxcommon** | `xxfin` / fin-base |
| **Fin-base** | same venv + `--with-downstream` | `xx_fin/` tests | — |

Core guard (before core pytest):

```python
import xxcommon
import importlib.util

assert importlib.util.find_spec('xxfin') is None
```

Local monorepo DX may use one venv with both packages; isolation is the pre-downstream assert in CI.

---

## PR / work sequencing

| Step | Repo | Scope | Status |
|------|------|--------|--------|
| **Phase 0** | xx-fin-domain | Packageize + `xx_fin/{xxfin,cxxfin}` layout | **Done** (`4205538`) |
| **Phase 1** | xx-fin-domain | Publish rehearsal (cxx + fin-base tags/wheels/index smoke) | **Done** |
| **PR0** | py10x | Promote `downstream` role, planner, opt-in `uv_sync`, constraints, tests | **Done** |
| **PR1** | py10x | Relocate `xx_fin/`, register downstream, publish workflows + CI downstream steps | **Done** |
| **PR2** | xx-fin-domain | Depend on published/editable fin-base; drop local `xx_fin/` | **Done** (attic + path sources) |
| **Release** | py10x | Coordinated fin-base (+ cxx) rcs from py10x via `xx-promote` | **Done** (through `0.1.0rc5`+) |

---

## Tests checklist

### Phase 1 (domain publish)

```bash
# after tags / index upload
python -m venv /tmp/fin-base-smoke && …/pip install py10x-fin-base
python -c "import xxfin; import cxxfin"
```

### Promote (PR0)

- Fin-base-only footprint → only fin-base acts; core has **no** forward pin for it.
- Core re-cut → fin-base pin lag acts.
- Optional second fake downstream in unit tests to prove N-package registry.

### Fin-base / isolation (PR1)

```bash
# Same CI job, sequential:
uv-sync py10x-core-dev --all-extras
python -c "import xxcommon; import importlib.util as u; assert u.find_spec('xxfin') is None"
pytest   # core suite (ignores xx_fin/ until fin-base is installed)
uv-sync py10x-core-dev --all-extras --with-downstream
python -c "import xxfin; import cxxfin"
pytest xx_fin/
```

### Domain (PR2)

```bash
uv sync --upgrade   # or editable bypass
pytest xxfin_commod … xxfin_positions … xxfin_testing …
```

---

## Risks

| Risk | Mitigation |
|------|------------|
| Accidental core→fin-base **published** pin | Core forward targets = siblings only; plan tests |
| Accidental `import xxfin` in core | Core CI without fin-base installed |
| Core re-cuts on fin-base-only edits | Footprint excludes `xx_fin/` |
| Fin deps bloat core | Live on fin-base / cxx pyprojects only |
| Treating `cxxfin` as a second product | Docs + metadata: install `py10x-fin-base` only |
| Domain dual-ship of `xxfin` | PR2 removes local `xx_fin/` after index has fin-base |
| Default `uv-sync` installs fin-base into core env | Downstream install **opt-in** |
| Parallel edits during path moves | Land layout moves quickly; use `git mv`; announce new paths |
| Shared root noise re-cuts both packages | Document same multi-package rule as cxx10x |

---

## Out of scope (this effort)

- Separate PyPI package for `xxcommon` / `py10x-common-domain`
- Nested packaging root for common
- Moving `xxfin_commod` / `xxfin_positions` into py10x (unless needed later)
- Multi-upstream pin rewriting between multiple downstreams (Phase B)
- New git repository for fin-base
- Making `py10x-fin-base-cxx` a supported standalone API

---

## Implementation checklist

### Phase 0 — domain packageize

- [x] `xx_fin/xxfin` + `xx_fin/cxxfin` layout (`git mv`)
- [x] `py10x-fin-base` / `py10x-fin-base-cxx` pyprojects + workspace wiring
- [x] Root depends on fin-base only; hatch drops `xxfin`
- [x] Retarget cxx cibuildwheel tags/paths
- [x] Boundary cleanup (`mkt_risk_proto`, stores split)
- [x] Track `xxfin_positions/dev_data_helpers/` on `main`

### Phase 1 — domain publish rehearsal

- [x] Pure-Python fin-base publish workflow — merged into cxx's, single `finbase_wheel.yml`
- [x] Cut cxx + fin-base rc tags; upload wheels — `py10x-fin-base-v0.1.0rc1`, both packages live on PyPI
- [x] Clean-venv `pip install py10x-fin-base` smoke — automated as a CI `smoke_test` job, not manual
- [x] Document version coordination (fin-base → cxx pin) — see `xx_fin/docs/OPEN_SOURCE_CHECKLIST.md`
- [x] Automate co-release `{name}-cxx==` pin via `xx-promote` (post-relocate)

### Promote tooling (PR0)

- [x] `[tool.dev_10x.downstream]` map + registry load (N packages; live `./xx_fin` entry)
- [x] `PkgInput` / `Plan` / `PrePlan` / `ProdPlan` three-role logic
- [x] Yank: refresh all downstreams when core yanked; yank downstream → core test-group only
- [x] `uv_sync` opt-in (`--with-downstream`) + constraints opt-in / refresh with `--with-downstream`
- [x] README + AGENTS.md §7
- [x] Plan / utils / uv_sync / constraints unit tests

### Relocate (PR1)

- [x] Move domain `xx_fin/` → `py10x/xx_fin/` (live tree under py10x; domain copy in `attic/xx_fin/`)
- [x] Register under `[tool.dev_10x.downstream]`
- [x] Core isolation collection: ignore `xx_fin/` unless `py10x-fin-base` is installed (`dev_10x.pytest_plugin`)
- [x] Downstream validation in CI (same job: isolation assert → core pytest → `--with-downstream` → `pytest xx_fin/`)
- [x] Publish workflows for fin-base (+ cxx) on py10x — `.github/workflows/finbase_wheel.yml` (triggers `pre|prod/py10x-fin-base-v*`)
- [x] Promote co-pins `{name}-cxx==` on fin-base release commits; fin-base `pytest11` entry point
- [x] Root/fin-base uv DX: fin-base owns workspace (`members = ["cxxfin"]`); core path-sources fin-base for lock/`test` group; `xx-constraints compile --with-downstream` for committed freeze
- [x] Docs / CHANGELOG refresh for relocate + install story

### Domain hard-cut (PR2)

- [x] Depend on published/editable `py10x-fin-base` (no local workspace member)
- [x] Drop local `xx_fin/` workspace members / tree (`git mv` → `attic/xx_fin/`)
- [x] Normal-mode `[tool.uv.sources]` editables → `../py10x` (+ `xx_fin` / `cxxfin`); BUILD-NOTES
- [x] Domain unit tests (smoke against attic-excluded pytest; see BUILD-NOTES)

### Release

- [x] `xx-promote pre` from py10x (coordinated fin-base + cxx rcs; e.g. through `0.1.0rc5`)
- [x] Confirm PyPI for fin-base (+ cxx)
- [x] Domain upgrade path (editables from `../py10x`; index for kernel/infra)

---

## Decisions log

| Decision | Choice |
|----------|--------|
| Common package extract | Cancelled; `xxcommon` stays in `py10x-core` |
| First product package | **`py10x-fin-base`** |
| Native impl dist name | **`py10x-fin-base-cxx`** (import remains `cxxfin`) |
| Publish shape | **C** — two wheels; consumers only install fin-base |
| Packageize before relocate | Yes — Phase 0 in domain first |
| Publish rehearsal before py10x move | Yes — Phase 1 in domain |
| Both Python + C++ co-located | Yes — under `xx_fin/`; same tree moves to py10x |
| Promote role | Downstream, not sibling |
| Core pins fin-base? | No published pin; unpublished `dependency-groups.test` only |
| Fin-base pins core? | Yes (published `==` / window via promote) |
| CI isolation | Same job: assert `xxfin` absent, run core suite, then `--with-downstream` + `xx_fin/` tests |
| Downstream tooling | Designed for N packages; fin-base is the first real entry |
