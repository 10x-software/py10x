# `dev_10x` — developer tooling for the 10x packages

Canonical documentation for release engineering and local dependency profiles.

- **Contributor workflow:** [`CONTRIBUTING.md`](../CONTRIBUTING.md)
- **Design rationale / Stage 2 roadmap:** [`DESIGN.md`](DESIGN.md)

## CLI tools

Declared in `[project.scripts]`:

| command              | purpose                                                                 |
|----------------------|-------------------------------------------------------------------------|
| `uv-sync`            | compatibility wrapper over `./xx-build` (install mode -> build mode)    |
| `uv-run`             | run a command in the prepared venv without `uv run` re-syncing          |
| `xx-promote`         | cut release candidates / final releases and yank them                     |
| `xx-constraints`     | regenerate or verify the committed third-party dependency freeze        |
| `xx-test-postgres-auth` | start/stop/status a local **password-auth** Postgres on port 5433 (Docker, falling back to Homebrew) |
| `xx-test-db-clean`   | drop `py10x_test*` databases left by killed test sessions |

Implementation: `dev_10x/uv_sync.py`, `dev_10x/uv_run.py`, `dev_10x/xx_promote.py`,
`dev_10x/xx_helpers.py`, `dev_10x/xx_ci.py`, `dev_10x/constraints.py`,
`dev_10x/postgres_local.py`, `dev_10x/db_clean.py`.

`xx-test-postgres-auth` leaves your trust instance on 5432 alone. It manages a second
cluster (user `postgres` / password `py10x_pg_auth` by default — a throwaway local test
fixture, override with `XX_PG_PASSWORD_AUTH_PASSWORD`) for infra with-auth smoke tests —
same contract as CI `.github/actions/setup-postgres`. Prefers a Docker container
(`postgres:15`, matching CI) when the Docker daemon is reachable; otherwise falls back to a
Homebrew-managed cluster under `~/pgdata-py10x-auth`.

`xx-test-db-clean` drops test databases left behind by killed sessions. Each pytest process
creates its own `py10x_test_<timestamp>_<pid>_<rand>` database on Postgres and Mongo and drops it at the
end (`core_10x/testlib/test_databases.py` + the root `conftest.py`), so nothing accumulates
and concurrent sessions never share state. A session killed before teardown — Ctrl-C, a
crash, a CI timeout — leaves its database behind. Dropping is a separate command rather than a flag, since it is
not reversible:

```bash
uv run --no-sync xx-test-db-clean list             # what is there
uv run --no-sync xx-test-db-clean drop             # drop it
uv run --no-sync xx-test-db-clean legacy           # test data predating per-session databases
uv run --no-sync xx-test-db-clean legacy --drop    # ... and remove it
```

Only names starting with `py10x_test` are candidates, so nothing of your own is at risk — but
a *running* session's database matches too, so do not `drop` while tests run elsewhere.
Set `XX_TEST_DB=<name>` to pin a session's database and keep it after the run for inspection.

`legacy` is a one-time migration aid: before per-session databases, tests wrote into fixed
Mongo databases (`test_db`, `test_filters_mongo`, `perf_test`) and into the Postgres server
default. On Postgres it only considers tables carrying the collection layout (`_id` / `_rev` /
`_data`), so tables of your own in that database are never candidates.

---

## The packages (siblings, core, downstreams)

They version **independently** and all live in this repo (the C++ siblings moved in from the former
`cxx10x` repo with their history and tags). Optional **downstreams** (packages that depend on core;
core does **not** publish a pin to them) are declared separately.

| role | package | path | tag prefix | published pins |
|------|---------|------|------------|----------------|
| core | `py10x-core` | `.` | `v` | `==` / windows onto **siblings only** |
| sibling | `py10x-kernel` | `cxx10x/core_10x` | `py10x-kernel-v` | none |
| sibling | `py10x-infra` | `cxx10x/infra_10x` | `py10x-infra-v` | none |
| downstream | `py10x-fin-base` | `xx_fin` | `py10x-fin-base-v` | `==` / windows onto **core** |

py10x-core depends on the siblings (forward). The siblings pin nothing: core is in the same tree,
so their CI tests them against core at the same commit. Core may track downstreams in its
unpublished PEP 735 **`[dependency-groups]` `test`** group (`py10x-fin-base>=…`) so an opt-in job can
install fin-base and run **its** suite against that core — without making fin-base importable in the
default core CI job (`--all-extras` does **not** pull `dependency-groups.test`).

| Role | Re-cut when | Yank side effects |
|------|-------------|-------------------|
| sibling | own footprint | refresh that sibling’s pin on **core** main |
| core | own footprint **or sibling** pin lag | refresh sibling pins on core **and** each downstream’s published `py10x-core` pin (+ core test-group) |
| downstream | own footprint **or core** pin lag | branch/tags + refresh **core’s test-group** pin; do **not** edit published core deps |

Layout: `[tool.dev_10x.siblings]` and optional `[tool.dev_10x.downstream]` (same `{name = {path=…}}`
shape; paths are in-repo). `xx_promote` / `env_check` / `constraints` all read both. Downstreams
are installed through the `test` / `test-extras` dependency groups (default in plain `uv sync`;
`uv-sync` leaves them out unless `--with-downstream`). Tag prefix defaults to `{name}-v`.

**Footprint.** A package re-cuts when its *footprint* changed since its last tag. By default that is
the whole repo minus the other packages' paths — shared files (CI, root config) count for core and
downstreams. A package can instead declare an explicit `footprint` (git pathspecs); the C++
siblings do, so core-only Python or CI edits never re-cut them, while shared `cxx10x/` build files
re-cut both:

```toml
py10x-kernel = { path = "cxx10x/core_10x", footprint = ["cxx10x", ":(exclude)cxx10x/infra_10x", ".github/workflows/cxx10x_wheels.yml", ".github/actions/build-wheels"] }
```

Explicit footprints are also excluded from every default footprint (core ignores `cxx10x/**`).

### setuptools-scm / hatch-vcs gotchas

- **Dirty tree → wrong version.** Any transient edit to `pyproject.toml` during an editable build
  makes scm stamp `X.Y.Z.devN+g<hash>.d<date>` instead of the tag version. Avoid editing pyproject
  during installs.
- **`0.1.dev1+g…` = NO tag found** (absolute fallback) — almost always a *shallow* checkout. CI that
  versions a co-dependency sibling needs `actions/checkout` `fetch-depth: 0`; the triggering tag is
  present even when shallow, other tags are not.
- **pre/prod rc tags are not on `main`.** Publishable rc/final tags live on tool-owned release
  branches: bare `pre`/`prod` for core; `pre-{name}` / `prod-{name}` for every other package (git
  cannot nest `pre/{name}` under bare `pre`). Each release tag gets a commit of its own — with two tags
  of one train on a commit, `git describe` picks by tag *name*, not version, and setuptools-scm
  could stamp the wrong version.
  `xx-promote pre` tags `main` HEAD with `{T}rc(N+1).dev` when cutting rcN (a setuptools-scm
  marker, not a release) so plain `git describe` / hatch-vcs on `main` stamps
  `0.2.1rc18.devM+g…` while rc17 lives on the release branch. `xx-promote prod` replaces that with
  `{next_micro(T)}rc0.dev` (e.g. `0.2.2rc0.dev` after final `0.2.1`) so `main` stays above the
  release and below the first rc of the next micro.
  Publish workflows trigger on **`pre/{release}`** / **`prod/{release}`** tags (same commit as the
  release tag); they listen on `pre/`/`prod/` publish triggers only.
- **Ordering:** always compare with `packaging.version.Version` (`max`), never
  `git --sort=-v:refname` / `sort -V` (they rank `0.2.3` *below* `0.2.3rc1`).

---

## `xx-promote` — release promotion

Releases are not cut by hand-editing pins. `main` always carries **rc-window pins** (updated by
`xx-promote` epilogues). `xx-promote` cuts
each release onto a tool-owned branch — bare `pre`/`prod` for core, `pre-{name}` for every other
package — writing **coordinated exact pins** there and tagging it, so
an external `pip install …rc1` resolves the coordinated sibling set. Branch/coordination model:
tool-owned release branches per package (see [Pin model](#pin-model-three-places) and
[Design rationale](DESIGN.md)).

`xx-promote` is a `core_10x.traitable_cli` tree: the command is a positional word and options use
the `--option value` form (dashes in names map to underscores, e.g. `--dry-run` → `dry_run`).
Boolean options also accept the `--option` / `--no-option` shortcuts (== `--option true` /
`--option false`). 

### Pin model (three places)

For a sibling at coordinated rc `rcN` or released final `T`:

- **`main` — rc-window forward pins (core → siblings):**
  - **After `pre`:** `>=rcN,<rc(N+1)` per sibling (upper bound is the **next rc**, exclusive — not
    `next_micro`). The inclusive rc floor auto-enables prereleases.
    Blocks a published `rc(N+1)` on the index while py10x `main` still pins the `rcN` line; pairs
    with the sibling's setuptools-scm marker `{T}rc(N+1).dev` on `main` (must stay in lockstep — see
    [Pin model](#pin-model-three-places)).
  - **After `prod`:** `>=T,<{next_micro(T)}rc1` — **not** `>=T,<next_micro>`. Admits the post-final
    marker editable (`{next_micro}rc0.dev`) and blocks the next publishable rc.
- **`pre` / `prod` — exact forward `==` (core → siblings, published):** core pins each sibling
  `==<coordinated version>` (`==X.YrcN` on `pre`, `==X.Y` on `prod`). This is the external
  coordination guarantee — an rc/final wheel drags in exactly the coordinated siblings. `==<pre>`
  auto-enables prereleases on its own; `==<final>` admits only that final, **not** its rc and **not**
  its `.postN` (stricter than the old `>=T,<N`, by design — see *Conscious tradeoffs* in [`DESIGN.md`](DESIGN.md)).
  Core never publishes a pin to downstreams.
- **downstream → core (published):** same `==` / window shapes as core→sibling, written onto the
  downstream’s `[project.dependencies]`.
- **downstream co-release `{name}-cxx` (published):** when a downstream product dist depends on an
  impl wheel with the same tag train (e.g. `py10x-fin-base` → `py10x-fin-base-cxx`), promote writes
  `==<coordinated downstream version>` on the release commit and keeps that exact pin on `main`
  (not a window). `write_forward_pins` only rewrites the dep if it already exists.
- **`test` group (core → downstreams; unpublished):** `py10x-fin-base>=…` (etc.) on core. `>=`
  not `==`: the prerelease token falls out for free. Uncapped but self-correcting via the
  downstream's forward `==` on core. Siblings carry no reverse pin (same tree as core).

> Why not one pin for everything? Whether uv auto-enables pre-releases is decided by the literal
> tokens in the specifier, so "dev-by-default but rc-when-released" cannot be a single static
> string — hence the explicit promotion step. Note also `>=Trc1,<T` is an **empty** set (`<T`
> excludes pre-releases of `T`); the tooling never emits it. All these pin forms are locked by
> assumption guards in `unit_tests/test_xx_utils.py` (coordination pin forms).

### Subcommands

```
xx-promote pre                                # cut the next coordinated rc onto the `pre` branch
xx-promote pre --next-version 0.3.0           # force core+siblings onto 0.3.0rc1 (coordinated bump)
xx-promote pre --next-version 0.3.0,X=2.0.0   # group at 0.3.0, package X at 2.0.0
xx-promote pre --next-version X=2.0.0,Y=1.5.0 # independently targeting X and Y
xx-promote pre --no-publish                   # cut without publish triggers (attach later)
xx-promote pre --publish-only                 # create missing publish triggers only (idempotent)
xx-promote prod                               # stack each final on its rc, onto the `prod` branch
xx-promote yank --pkg <name> --version <ver>  # yank the latest tag (rc or final)
xx-promote status                             # pending promotions: tagged but not yet on PyPI
xx-promote resync                             # recovery: force local managed refs to match origin
```

Re-cut decisions are **declarative** (a pure planner, `xx_plan.plan_pre_batch` / `plan_prod_batch`):
they compare persistent state (tags + current pins), so a run is **idempotent** — re-running after a
crash re-derives the plan from current tags and resumes.

**`local == remote` invariant + atomic recovery.** A real run **starts** synced and (with `--push`)
**finishes** synced; crash recovery is "discard local, resync, re-run", not in-place repair:

- *Start (precondition):* `GitHelpers.require_synced` requires **local == origin** before a real
  run: committed work pushed (`main == origin/main`, managed tags match `origin`; untracked files are OK). 
  It **refuses** on un-pushed `main`,
  divergent tags, or dirty tracked files — a release is never cut from un-synced state. (No
  `origin` → local-only dev; the remote half is skipped.)
- *Finish:* with `--push`, promote refs (branches, release tags, dev-marker drop+create, `main`) are
  pushed in **one atomic push** (all packages share the repo, so a partial cross-package push is
  unreachable). **Publish triggers** use `isolated_tags_to_push` — one
  refspec per `git push` — so CI tag-create webhooks always fire. Release tags are never deleted
  for CI.
- *Recovery:* after a crash, `require_synced` refuses until local == remote. Run **`xx-promote
  resync`** — it forces `main`, every `pre`/`prod` release branch, and managed tags back to `origin`
  (discarding local-only work) — then re-run. If release tags landed but publish triggers did not,
  use **`xx-promote pre --publish-only --push`** (or `prod --publish-only`) to create any missing
  publish triggers (non-force `git tag`; **idempotent** — exits successfully with
  "All publish triggers already present" when nothing is missing). There is **no in-place
  reconcile** — the atomic push makes the states it used to repair unreachable.
- *Without `--push`:* local diverges from `origin` by design — **push manually** (`git push`) to
  re-sync, or re-run with `push=true`.

- **`pre`** (`--from=main`) cuts the next coordinated rc. A package is re-cut when its footprint
  changed since its last tag ([footprint](#the-packages-siblings-core-downstreams); epilogue pin and
  test-group edits to first-party pyprojects don't count), **or**, for core, when its forward `==` pin lags a
  sibling's latest tag (so a fresh sibling rc forces a core re-cut). For each re-cut package it tags
  `main` HEAD with `{T}rc(N+1).dev` (setuptools-scm marker for the next rc line), writes
  the coordinated pins (core → siblings `==X.YrcN`; siblings: none) on a commit forked
  from `main` HEAD, **force-resets** the package's `pre` branch to it, and tags `v{T}rc{n}`. A
  **`pre/{tag}` publish trigger** on that commit starts the publish workflow (omit with `--no-publish`,
  attach later with `--publish-only`). Footprint
  is diffed from the tag's fork-point on `main` (so the pin commit itself never counts as a change).
  Unchanged packages are skipped; a latest tag that is still an rc is offered for `--push`.
  On `main`, the epilogue writes **rc-window** pins (`>=rcN,<rc(N+1)`) for each sibling from the
  batch's coordinated versions.
  **`--next-version`** replaces the auto `next_micro(latest_final)` target. A bare `X.Y.Z` sets
  **core and every sibling** (coordinated bump: `0.2.3rcN` → `--next-version 0.3.0` cuts `0.3.0rc1`).
  `name=X.Y.Z` sets one package (a sibling, or a downstream). Comma-separate them; a later entry wins
  for the same name, and a bare token rewrites the whole group, so put it first
  (`0.4.0,py10x-kernel=0.5.0`, or `0.4.0,py10x-fin-base=0.2.0` for a downstream outside the group).
  Each overridden package re-cuts even with an unchanged footprint; the rest of the batch still
  coordinates by the normal rules (a forced re-cut can still pull others forward via pin-lag). Every
  version must be a plain `X.Y.Z` release (no rc/dev/post) strictly greater than its package's latest tag.
- **`prod`** (per package whose **latest** tag is an rc): force-updates
  the `prod` branch onto that rc commit, **stacks** a final-pin commit there (core → siblings
  exact `==X.Y` of the rc's base — `0.3.0rc1` → `0.3.0`, not `next_micro(latest_final)`; siblings
  get an empty commit), and tags `v{T}`. `--next-version` is **pre-only**. Then on `main` it
  retags `{next_micro(T)}rc0.dev` (dropping the stale rc-line marker), writes py10x-core's **post-final
  window** pins (`>=T,<{next_micro}rc1`), and points core's test group at released downstreams.
  **`prod/{tag}` publish triggers** on each final commit. Released
  **source** == rc source — the final commit only rewrites pins on top of the rc.
- **`yank`** renames the **latest** tag to `<tag>_yanked` (deletes its publish trigger too;
  workflows listen on `pre/`/`prod/` only), force-rolls the affected `pre`/`prod` pointer back to the previous tag of
  the same kind (rc→`pre`, final→`prod`), and rolls back py10x-core **`main` forward pins** to
  match the latest non-yanked release tag (rc-window or post-final window as appropriate). When
  yanking **core**, all sibling forward pins are refreshed; when yanking a sibling, only that
  sibling's pin is updated. Prints **manual PyPI yank instructions** only when the version is
  already on the index (PyPI has no public yank API). `{T}rc(N+1).dev` markers on `main` are
  **left in place** (the next rc is still N+1). Yanking an older release is refused (needs
  `--cascade`, a Stage-2 feature). A yanked version number is **consumed** — generation floors on
  `max(all tags incl. yanked)` so it is never reused — while selection still ignores `*_yanked`
  and `*.dev` main markers. No yank CI workflows.
- **`status` - compares local tags (rc + final; `*_yanked` and `*.dev` main markers excluded)
  against PyPI and reports tags
  pushed **since the latest PyPI release** that are not on the index yet. Publish is atomic in CI
  (the workflow uploads to PyPI), so a version on the index is treated as successfully published;
  the floor is simply `max(published)`. Superseded rc attempts before that floor and abandoned
  pre-PyPI history are intentionally ignored. For each pending tag it prints the publish workflow
  state (`in_progress` / `queued` / `failure` / `success` …) and a link to the run — that is how
  you tell whether a tagged-but-unpublished rc is still running or failed.

### Safety levels (every subcommand, as `--option` flags)

| flag         | effect                                                                       |
|--------------|------------------------------------------------------------------------------|
| `--dry-run`  | print the full plan; change **nothing** (local or remote)                    |
| *(default)*  | apply **local** changes only — inspect with `git log`/`status`, reset to undo |
| `--push`     | apply locally, then push to remotes **last**, only after all local steps pass |

`dry_run` always wins. Before any real change the repos must be **synced with `origin`**
(committed and pushed: `main` and managed tags match remote, untracked files are OK — see
the `local == remote` invariant above); `--push` re-syncs the
remote at the end, otherwise push manually. `--base <path>` overrides the py10x repo root (default:
cwd). Always preview first:

```
xx-promote prod --dry-run
xx-promote prod --push
```

---

## `xx-build` and plain `uv` — development environment

From the repo root (bash; Git Bash on Windows):

```bash
./xx-build init                    # fresh clone (build mode: dev)
./xx-build init --mode ci-release  # ... in another build mode
./xx-build init --clean            # start over (also after `uv venv --clear` or deleting build/)
./xx-build set-mode dev-release    # switch build mode, rebuild
./xx-build show-mode               # active mode; fails if uv.toml is out of date
uv sync                            # from then on: keep the env current, in the active mode
uv run pytest -q
```

Plain `uv sync` installs the default dependency groups (`dev`, `extras`, `test`, `test-extras`):
py10x-core with all its extras, plus py10x-kernel / py10x-infra / py10x-fin-base / py10x-fin-base-cxx
editable from this tree. The C++ packages build without isolation into `build/py10x-build/` (next to
`.venv`, so it survives `uv venv --clear`), one build dir per build type.

`init` exists because a fresh environment needs an order uv cannot express on its own: the C++
toolchain (the `build` group, from `uv.lock`) first, since the C++ packages build without isolation;
then py10x-kernel / py10x-infra, since py10x-fin-base-cxx's build needs an installed kernel; then
everything else. It refuses to run over an existing `.venv` or `build/`; `--clean` deletes both
first. Extra arguments go to its `uv sync` calls (e.g. `--locked`, `--no-group test`). `./xx-build`
is a script at the repo root rather than a `[project.scripts]` command because it runs before the
venv exists (implementation: `dev_10x/xx_build.py`).

`uv.lock` is committed: change it only as described under
[constraints](#constraintstxt--reproducibility), never with `uv sync --upgrade` / `uv lock --upgrade`.

### Build modes

| mode | C++ packages | use |
|------|--------------|-----|
| `dev` (default) | Debug, editable, rebuild-on-import | everyday development: C++ edits take effect on the next import |
| `dev-release` | Release, editable, rebuild-on-import | developing against optimized builds |
| `ci-release` | Release, editable, no rebuild on import | CI and the Docker image: built once, so no per-import rebuild check (and the build dir may go) |

`dev` is `[tool.uv]` in `pyproject.toml` as is (each C++ package's own defaults: Debug,
`editable.rebuild = true`). The other modes are tables under `[tool.dev_10x.modes]`:
`./xx-build set-mode <mode>` writes a gitignored `uv.toml` = a copy of `[tool.uv]` (minus `sources`,
`default-groups` and the other fields uv reads only from `pyproject.toml`) with the mode's
`config-settings-package` merged in, then rebuilds in `init`'s order. uv takes `uv.toml` in place of
`[tool.uv]` - and says so in a warning on every command while a non-default mode is active.
`./xx-build set-mode dev` deletes `uv.toml`; build dirs are per build type, so switching back reuses
the Debug build.

`uv.toml` is a copy: after editing `[tool.uv]` or a mode, re-run `./xx-build set-mode <mode>`.
`./xx-build show-mode` prints the active mode and fails, naming that command, when `uv.toml` no
longer matches what `set-mode` would write.

Sanitizers are a separate switch: `XX_CXX_SANITIZERS=ON` (an env var and a C++ cache key, in any
mode). The Windows MSVC toolset pin is not part of any mode either: it lives in each C++ package's
`pyproject.toml`. cibuildwheel (published wheels) builds in isolation with its own settings: a
throwaway build dir, no rebuild, Release.

On Windows, an import that rebuilds fails while another process still holds the old extension, and
works again once that process exits. Under pytest, `dev_10x/pytest_plugin.py` rebuilds once in the
main process and has xdist workers skip the check (`SKBUILD_EDITABLE_SKIP`).

`python -m dev_10x.env_check [MODE] [--downstream]` asserts the venv holds what a mode installs
(source tree, editable, rebuild-on-import, build type) and imports the C++ modules; with no MODE it
checks the active one. CI runs it after every install (`ci.yml`'s install-modes job walks all modes).

---

## `uv-sync` / `uv-run` — compatibility wrappers

`uv-sync py10x-dev [--all-extras] [--with-downstream] [uv sync args...]` (`dev_10x/uv_sync.py`) is a
thin wrapper over `./xx-build`, kept for CI (`ci-test-suite`, `refresh-constraints.yml`) and existing
habits. `$XX_UV_INSTALL_MODE` picks the build mode:

| `XX_UV_INSTALL_MODE` | build mode |
|----------------------|------------|
| `incremental_quiet` (default), `incremental` | `dev` |
| `editable`, `normal` | `ci-release` |

and the arguments pick the dependency groups: without `--all-extras` it adds `--no-group extras`,
without `--with-downstream` `--no-group test --no-group test-extras` (so xxfin is not importable -
core CI's isolation check). It then runs `./xx-build set-mode <mode>` (`init --mode <mode>` without a
`.venv`), passing other arguments on to `uv sync`. `--upgrade` is dropped (uv.lock changes only
through `xx-constraints compile`); the `user` / `domain-dev` profiles are gone - a domain repo syncs
against py10x with its own `uv sync`.

`uv-run <command>` is `uv run --no-sync <command>`.

---

## `constraints.txt` — reproducibility

**Do not `==`-pin `[project.dependencies]`** in published metadata. py10x-core is a library; exact
pins cause consumer conflicts and do not pin transitives anyway. Keep **ranges** in published
metadata.

**The freeze is the committed `uv.lock`** (universal: every supported Python and platform, all
extras and dependency groups, downstreams included through the `test` / `test-extras` groups).
**`constraints.txt` is generated from it** with `uv export`: the same pins as a reviewable
`name==version` list. `uv sync` (dev, and CI through `uv-sync`) installs exactly `uv.lock`;
`build.yml` and `cxx10x_wheels.yml`, which use `uv pip install`, pass `-c constraints.txt`. Never edit
either file by hand.

Lock changes come only from pyproject edits (`xx-constraints compile`) or the weekly refresh
workflow. **Never run `uv sync --upgrade` / `uv lock --upgrade` locally** to update the freeze; it
would rewrite `uv.lock` outside that flow. Neither file counts towards any package's release footprint, so a freeze refresh alone never
re-cuts a package. `uv.lock` is marked `linguist-generated` in
`.gitattributes`, so GitHub collapses its diff: review `constraints.txt` instead. Lock files from
different uv minor versions differ (e.g. 0.12 vs 0.13), so commit locks written by a uv satisfying
`[tool.uv] required-version`, and raise that minimum if versions start fighting over the file.

### `xx-constraints`

```
xx-constraints compile              # conservative: `uv lock`, then regenerate constraints.txt
xx-constraints compile --upgrade    # `uv lock --upgrade`: bump all pins to latest within ranges
xx-constraints check                # assert the active env is fully frozen against constraints.txt
xx-constraints check-export         # assert constraints.txt == `uv export` of uv.lock
```

- **`compile`** runs `uv lock` (or `uv lock --upgrade`), then writes `constraints.txt` from
  `uv export --frozen --all-extras --all-groups --no-hashes`, with `--no-emit-package` for each
  first-party name (root, siblings, downstreams, and `[tool.uv.workspace]` members under the repo
  root and each sibling/downstream packaging root — e.g. fin-base’s `cxxfin` →
  `py10x-fin-base-cxx`; derived via `_first_party`, not a hardcoded list).
  - **Default (no `--upgrade`)**: conservative — `uv lock` keeps every existing pin that still
    satisfies the ranges; only changes what a pyproject edit forces. Use after adding or changing
    a dependency, and commit `pyproject.toml`, `uv.lock` and `constraints.txt` together.
  - **`--upgrade`**: re-resolves every pin to the latest version allowed by the ranges. Used by
    `refresh-constraints.yml`.
  - **`--summary-file PATH`** writes uv's `Updated X v1 -> v2` lines (the refresh PR description).
  - `--with-downstream [name…]` is still accepted and ignored: the lock always covers downstreams.
  - uv runs as `$UV` when set (inside `uv run`), so a venv-installed uv — licensecheck pulls one on
    Python 3.11 — never replaces the uv that ran the command.
- **`check`** asserts every *installed* third-party dist (minus the first-party packages) is
  pinned in `constraints.txt`. Runs in `ci.yml` and `build.yml` — the enforcement point when a
  sibling adds a dep without a regen.
- **`check-export`** asserts `constraints.txt` is exactly the export of `uv.lock`. Runs in `ci.yml`,
  next to `uv lock --check` (fails when `uv.lock` is stale against a pyproject edit).

**Known tradeoff:** a sibling needing a version outside the pin hits a hard conflict → regenerate
(`xx-constraints compile`) and commit both files.

dependabot keeps pins fresh — orthogonal to reproducibility (update vs freeze).

### `refresh-constraints.yml` — scheduled `xx-upgrade`

`.github/workflows/refresh-constraints.yml` automates the *update* side on a **weekly** cron
(Mon 04:00 UTC, plus `workflow_dispatch`) **without** eroding the freeze:

1. Sync `py10x-dev`, then `xx-constraints compile --upgrade`: `uv lock --upgrade` against the
   latest compatible PyPI graph (siblings + in-tree downstream packaging roots), and
   `constraints.txt` regenerated from the lock.
2. If neither `uv.lock` nor `constraints.txt` changed → stop (no tests, no PR).
3. If they changed → re-sync against the fresh pins (compile rewrites the files but does not
   reinstall), `xx-constraints check`, then the **full test suite** (CI-provisioned MongoDB replica
   set + Playwright), mirroring `ci.yml`.
4. Only on green → open/update PR `chore: refresh constraints.txt` with `uv.lock` and
   `constraints.txt`, and uv's list of updated packages in the description. The PR is review-gated
   and merged by a human.

So `main` never auto-changes, the proposed freeze is green-by-construction, and a **red run is the
alert** that an upstream release broke us (do not merge — investigate the pin). Notes:

- The workflow mints a short-lived GitHub App installation token via
  `actions/create-github-app-token@v3` (repo variable **`REFRESH_CONSTRAINTS_APP_CLIENT_ID`**, repo
  secret **`REFRESH_CONSTRAINTS_APP_PRIVATE_KEY`**; Contents + Pull requests + Issues write) so the
  opened PR is authored by the App and still gets its own CI run. The in-run suite remains the
  gate before the PR is opened.
- Failure notifications follow GitHub's default scheduled-workflow rules (the cron's last editor);
  add an explicit Slack/issue step for team-wide alerting.

---

## CI release gates

### py10x `build.yml` (`test` → `publish`)

On **`pre/v*`** / **`prod/v*`** publish-trigger tag push:

1. Full-history checkout (`fetch-depth: 0`: sibling release tags and their commits).
2. Resolve each sibling tag via `python -m dev_10x.xx_ci latest_tag` (kernel-free — only
   `packaging` + `tomlkit`).
3. `uv pip install` siblings from this checkout at those tags
   (`git+file://$PWD@<tag>#subdirectory=cxx10x/…`).
4. `uv pip install -e . --all-extras --requirements pyproject.toml -c constraints.txt`.
5. `xx_ci verify_sibling` for kernel and infra.
6. Full pytest suite.
7. `uv build`, then `xx_ci wait_sibling_releases` (up to 60 min) until the kernel/infra versions core
   `==`-pins are on PyPI — they publish from `cxx10x_wheels.yml`, so core must not reach the index
   first (an rc whose pinned siblings never land is uninstallable) — then `uv publish`.

### `cxx10x_wheels.yml` (kernel / infra publish)

On **`pre|prod/py10x-kernel-v*`** / **`pre|prod/py10x-infra-v*`** publish-trigger tag push (the
package comes from the tag; `workflow_dispatch` builds one package without uploading):

1. **test**: full-history checkout; install core editable with **both** siblings built from this
   commit, passed as `--override`s (core's `main` pins at a sibling release commit still name the
   previous rc window); assert the built version equals the tag; run core's suite with the same
   services as `build.yml` (Mongo replica set, Postgres, Playwright; `XX_TEST_STRICT=1`).
2. **build_wheels**: cibuildwheel on ubuntu x86_64 / aarch64, macOS universal2, windows-2025.
3. **upload**: trusted PyPI publish (OIDC). The PyPI trusted publishers for `py10x-kernel` and
   `py10x-infra` point at `10x-software/py10x`, workflow `cxx10x_wheels.yml`.

PR / push CI additionally runs the `cxx10x/tests` harness suites (`ci.yml` job `cxx10x-tests`).

### Downstream validation (fin-base)

Same CI job as the core suite ([`.github/actions/ci-test-suite`](../.github/actions/ci-test-suite/action.yml)), sequential steps:

| Step | Env | Check |
|------|-----|--------|
| **Core isolation** | siblings + core; **no** `--with-downstream` | `find_spec('xxfin') is None`, then core / ui / infra / dev / xxcommon pytest |
| **Downstream** | same venv + `uv-sync py10x-dev --all-extras --with-downstream` | `import xxfin; import cxxfin`, then `pytest xx_fin/` |

Do not install fin-base before the core suite — that would break isolation. Default `pytest`
ignores in-repo downstream trees (`xx_fin/`, from `[tool.dev_10x.downstream]`) unless that dist
is installed; editable core installs fall back to hatch wheel package names for the owned-top
filter.

### py10x `finbase_wheel.yml` (downstream publish)

On **`pre/py10x-fin-base-v*`** / **`prod/py10x-fin-base-v*`** publish-trigger tag push (same job
shape as the former domain `finbase_wheel.yml`):

1. cibuildwheel `xx_fin/cxxfin` on ubuntu / macos / windows-2025 → `py10x-fin-base-cxx` wheels.
   The isolated build is constrained (`PIP_CONSTRAINT`) to the siblings coordinated with this
   release (`xx_ci downstream_build_constraints`, which waits for them on PyPI): cxxfin's own
   build requirement is just `py10x-kernel>=0.0.0rc0`, and a cxxfin built against a kernel with
   different pybind11 internals cannot take its types.
2. Validate committed co-release pin (`py10x-fin-base-cxx (==<version>)`, written by xx-promote);
   `uv build --directory xx_fin` → `py10x-fin-base` sdist + wheel.
3. Per-OS clean-venv smoke: install both artifacts → `import xxfin; import cxxfin`, then pass a
   kernel `BDateCurve` into cxxfin (a kernel mismatch still imports, but fails that call).
   Before install, polls PyPI (up to 30 min) for the fin-base wheel’s exact `py10x-core==…`
   **and** that core’s forward-pinned siblings (`py10x-kernel` / `py10x-infra`) — see
   `.github/scripts/wait_finbase_pypi_deps.py`.
4. Trusted PyPI publish (OIDC) of all artifacts.

PyPI trusted publishers for `py10x-fin-base` and `py10x-fin-base-cxx` point at this repo
(`10x-software/py10x`) and workflow `finbase_wheel.yml`. The former domain-repo publishers were
removed.

### CI gotchas

- Every checkout that builds kernel/infra needs `fetch-depth: 0`: their setuptools-scm versions
  come from this repo's `py10x-{kernel,infra}-v*` tags.
- Use `python -m dev_10x.uv_sync` (or `./xx-build`) in CI, not `uvx --from ".[dev]" uv-sync`: `uvx`
  resolves `pyproject.toml` sibling deps from PyPI when installing the tool, which fails while `main`
  pins are ahead of the index.
- `uv pip install --all-extras` needs an explicit source:
  `-e . --all-extras --requirements pyproject.toml` (unlike `uv sync`).
- Tag triggers: **`pre/py10x-kernel-v*`** / **`prod/…`** (and core **`pre/v*`** / **`prod/v*`**).
  The old trigger tags imported from the former cxx10x repo fire nothing: the workflow at those
  commits lives under `cxx10x/.github/`, which GitHub ignores.
- Never `==`-pin published `[project.dependencies]`.

---

## `xx_ci.py` — kernel-free CI shim

`core_10x/__init__.py` imports `py10x_kernel`, so **anything that imports `core_10x` needs the
compiled kernel.** Tag resolution and sibling verification in publish CI must run *before* siblings
are installed — hence `dev_10x/xx_ci.py` uses only `packaging` and `tomlkit`. For local/ad-hoc use,
bootstrap via `uv run --no-project --with packaging --with tomlkit --with setuptools-scm`, or set up
the dev env first (`./xx-build init`).

```
python -m dev_10x.xx_ci latest_tag py10x-kernel
python -m dev_10x.xx_ci verify_sibling py10x-kernel
python -m dev_10x.xx_ci wait_sibling_releases   # on a pre/prod release commit
python -m dev_10x.xx_ci downstream_build_constraints xx_fin/pyproject.toml cibw-constraints.txt
```

---

## Design rationale and Stage 2 roadmap

Split out to [`DESIGN.md`](DESIGN.md) — why the release model looks the way it does, alternatives
considered, conscious tradeoffs, and what Stage 2 would add.
