# `dev_10x` — developer tooling for the 10x packages

Canonical documentation for release engineering and local dependency profiles.  
See also `AGENTS.md` §7 for agent-specific guardrails when editing this code.

## CLI tools

Declared in `[project.scripts]`:

| command           | purpose                                                                 |
|-------------------|-------------------------------------------------------------------------|
| `uv-sync`         | prepare the venv for a chosen *dependency-source profile*               |
| `uv-run`          | run a command in the prepared venv without `uv run` re-syncing          |
| `xx-promote`      | cut release candidates / final releases and yank them                     |
| `xx-constraints`  | regenerate or verify the committed third-party dependency freeze        |

Implementation: `dev_10x/uv_sync.py`, `dev_10x/uv_run.py`, `dev_10x/xx_promote.py`,
`dev_10x/xx_helpers.py`, `dev_10x/xx_ci.py`, `dev_10x/constraints.py`.

---

## The three packages

They version **independently** and live in two git repos:

| package        | repo / path                | tag prefix         | tags                         |
|----------------|----------------------------|--------------------|------------------------------|
| `py10x-core`   | `py10x` (this repo)        | `v`                | finals/rc on `pre`/`prod`; `{T}rc(N+1).dev` on `main` after `pre`; `{next_micro(T)}rc0.dev` after `prod` |
| `py10x-kernel` | `cxx10x` / `core_10x`      | `py10x-kernel-v`   | same pattern |
| `py10x-infra`  | `cxx10x` / `infra_10x`     | `py10x-infra-v`    | same pattern |

py10x-core depends on the other two (forward). For testing, kernel/infra carry a *dev-only*
reverse dependency on py10x-core via a PEP 735 **`[dependency-groups]` `test`** group — which is
**not** published in wheel metadata, so the dependency cycle never reaches consumers.

Sibling layout is declared once in `pyproject.toml` `[tool.dev_10x.siblings]` (path per sibling);
`dev_10x/xx_promote.py:packages()` and `dev_10x/uv_sync.py:packages()` both read it. Git URLs are
derived from `origin` (not hardcoded). Tag prefix defaults to `{name}-v`; repo root via
`git rev-parse --show-toplevel`.

### setuptools-scm / hatch-vcs gotchas

- **Dirty tree → wrong version.** Any transient edit to `pyproject.toml` during an editable build
  makes scm stamp `X.Y.Z.devN+g<hash>.d<date>` instead of the tag version. Avoid editing pyproject
  during installs (a core reason for the `uv-sync` pip-install redesign).
- **`0.1.dev1+g…` = NO tag found** (absolute fallback) — almost always a *shallow* checkout. CI that
  versions a co-dependency sibling needs `actions/checkout` `fetch-depth: 0`; the triggering tag is
  present even when shallow, other tags are not.
- **pre/prod rc tags are not on `main`.** Publishable rc/final tags live on tool-owned `pre`/`prod`
  branches. `xx-promote pre` tags `main` HEAD with `{T}rc(N+1).dev` when cutting rcN (a
  setuptools-scm marker, not a release) so plain `git describe` / hatch-vcs on `main` stamps
  `0.2.1rc18.devM+g…` while rc17 lives on `pre`. `xx-promote prod` replaces that with
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
each release onto a tool-owned branch — `pre` (current rc) / `prod` (current final), per package —
writing **coordinated exact pins** there and tagging it, so an external `pip install …rc1` resolves
the coordinated sibling set. See `docs/rc-branch-promotion.md` for the full branch/coordination model.

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
    with the setuptools-scm marker `{T}rc(N+1).dev` on cxx10x `main` (must stay in lockstep — see
    `docs/rc-branch-promotion.md`).
  - **After `prod`:** `>=T,<{next_micro(T)}rc1` — **not** `>=T,<next_micro>`. Admits the post-final
    marker editable (`{next_micro}rc0.dev`) and blocks the next publishable rc.
- **`pre` / `prod` — exact forward `==` (core → siblings, published):** core pins each sibling
  `==<coordinated version>` (`==X.YrcN` on `pre`, `==X.Y` on `prod`). This is the external
  coordination guarantee — an rc/final wheel drags in exactly the coordinated siblings. `==<pre>`
  auto-enables prereleases on its own; `==<final>` admits only that final, **not** its rc and **not**
  its `.postN` (stricter than the old `>=T,<N`, by design — see *Conscious tradeoffs* in the design note).
- **reverse `test` group (sibling → core, dev-only / unpublished):** `py10x-core>=<coordinated core>`.
  `>=` not `==`: the prerelease token falls out for free — `>=Trc` admits core prereleases (an rc
  sibling tests the prerelease line), `>=T` admits only finals. Uncapped but self-correcting via the
  forward `==`.

> Why not one pin for everything? Whether uv auto-enables pre-releases is decided by the literal
> tokens in the specifier, so "dev-by-default but rc-when-released" cannot be a single static
> string — hence the explicit promotion step. Note also `>=Trc1,<T` is an **empty** set (`<T`
> excludes pre-releases of `T`); the tooling never emits it. All these pin forms are locked by
> assumption guards in `unit_tests/test_xx_utils.py` (coordination pin forms).

### Subcommands

```
xx-promote pre                                # cut the next coordinated rc onto the `pre` branch
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
  pushed **once per repo, atomically**. **Publish triggers** use `isolated_tags_to_push` — one
  refspec per `git push` — so CI tag-create webhooks always fire. Release tags are never deleted
  for CI.
- *Recovery:* after a crash, `require_synced` refuses until local == remote. Run **`xx-promote
  resync`** — it forces each repo's `main`/`pre`/`prod` branches and managed tags back to `origin`
  (discarding local-only work) — then re-run. If release tags landed but publish triggers did not,
  use **`xx-promote pre --publish-only --push`** (or `prod --publish-only`) to create any missing
  publish triggers (non-force `git tag`; **idempotent** — exits successfully with
  "All publish triggers already present" when nothing is missing). Cross-repo (siblings pushed, core not) surfaces as one
  un-synced repo; resync it and the idempotent re-run resumes (core re-cuts to coordinate). There is
  **no in-place reconcile** — atomic pushes make the states it used to repair unreachable.
- *Without `--push`:* local diverges from `origin` by design — **push manually** (`git push`) to
  re-sync, or re-run with `push=true`.

- **`pre`** (`--from=main`) cuts the next coordinated rc. A package is re-cut when its footprint
  changed since its last tag (`GitHelpers.diff_pathspecs`: source subtree **plus** the
  `.github/workflows/{subdir}*` publish workflow), **or**, for core, when its forward `==` pin lags a
  sibling's latest tag (so a fresh sibling rc forces a core re-cut). For each re-cut package it tags
  `main` HEAD with `{T}rc(N+1).dev` (setuptools-scm marker for the next rc line), writes
  the coordinated pins (core → siblings `==X.YrcN`; sibling → `py10x-core>=X.YrcN`) on a commit forked
  from `main` HEAD, **force-resets** the package's `pre` branch to it, and tags `v{T}rc{n}`. A
  **`pre/{tag}` publish trigger** on that commit starts the publish workflow (omit with `--no-publish`,
  attach later with `--publish-only`). Footprint
  is diffed from the tag's fork-point on `main` (so the pin commit itself never counts as a change).
  Unchanged packages are skipped; a latest tag that is still an rc is offered for `--push`.
  On `main`, the epilogue writes **rc-window** pins (`>=rcN,<rc(N+1)`) for each sibling from the
  batch's coordinated versions.
- **`prod`** (per package whose **latest** tag is a pre-release with an rc for its target): force-updates
  the `prod` branch onto the latest rc commit, **stacks** a final-pin commit there (core → siblings
  exact `==X.Y`; sibling → `test = ["py10x-core>=X.Y"]`), and tags `v{T}`. Then on `main` it
  retags `{next_micro(T)}rc0.dev` (dropping the stale rc-line marker), writes py10x-core's **post-final
  window** pins (`>=T,<{next_micro}rc1`), and points the reverse groups at the released core.
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

## `uv-sync` / `uv-run` — local dependency profiles

### Design

`uv-sync` drives **`uv pip install` directly** instead of transiently rewriting
`pyproject.toml` `[tool.uv.sources]` and running `uv sync`. Nothing edits pyproject, so the tree
stays clean → setuptools-scm never stamps a dirty guess-next-dev version → py10x-core (and the slow
`playwright install` hook) is rebuilt only when its source version actually changes.

Every `uv pip install` passes **`-c constraints.txt`** (see [constraints](#constraintstxt--reproducibility)
below).

`uv-run <command> [args…]` is `uv run --no-sync …` — the venv is already prepared by `uv-sync`;
`uv run` must not re-sync and reconcile sources back to bare `pyproject.toml`.

The active profile is recorded in `.dev_10x_profile` (informational).

### Profiles

| profile          | py10x-core      | py10x-kernel / py10x-infra |
|------------------|-----------------|----------------------------|
| `user`           | local editable  | released wheels (index)    |
| `domain-dev`     | git `main`      | git `main`                 |
| `py10x-dev`      | local editable  | git `main`                 |
| `py10x-core-dev` | local editable  | local editable (`../cxx10x`)|

```
uv-sync py10x-core-dev --all-extras    # typical full dev setup
uv-run pytest -q                       # run in the prepared venv
```

### Install order

1. **Siblings** (local or git) — install only when [reinstall rules](#reinstall-rules) say so.
   For **local** siblings, `uv pip install -e <path> "<name> (<pin from pyproject>)"` on one command
   so a lagged editable below the rc-window floor fails resolve instead of silently pulling the index.
   Index siblings are resolved in step 2; `--reinstall-package` forces a swap if currently editable/git.
2. **`uv pip install --requirements pyproject.toml`** (+ caller args such as `--all-extras`) —
   core's deps and extras, additive (keeps step-1 siblings). Rc-window pins block index rc upgrades.
3. **py10x-core itself** (local editable, or git for `domain-dev`) — install only if needed.

### Reinstall rules

Applied per package (`need_install` in `dev_10x/uv_sync.py`):

| condition | action |
|-----------|--------|
| not installed | reinstall |
| git source profile | always reinstall |
| switching to index from non-index | reinstall (via `--reinstall-package` in step 2) |
| local editable path changed | reinstall |
| local editable: installed version ≠ setuptools-scm of source | reinstall |
| `XX_UV_INCREMENTAL` toggled | force reinstall of local C++ siblings |

**Source detection** uses PEP 610 `direct_url.json`: absent → index; `dir_info.editable` → local
(compare path); otherwise → git/other. The version-skip optimization matters for editable installs
(expensive C++/playwright); index and git wheels are cheap to reinstall.

After install, a **PEP 610 editable guard** raises if a profile expects a local sibling but the
installed dist came back non-editable (pin pulled an index build).

Git URLs are derived from the sibling `path` and `origin` (`_swap_repo` preserves SSH vs HTTPS).
Branch from `[tool.dev_10x] branch` (default `main`).

Extras are **not** forced — pass `--all-extras` / `--extra X` as `uv-sync` args (they bind to the
step-2 `--requirements pyproject.toml` install).

`py10x-core-dev` also runs `playwright install chromium` when needed.

### `XX_UV_INCREMENTAL=1`

When set **and** the active profile uses local-editable C++ packages, kernel/infra switch to
no-build-isolation incremental builds:

- `--no-build-isolation-package <pkg>`
- `--config-settings-package <pkg>:build-dir=.venv/py10x-build/<pkg>/{wheel_tag}`
- `--config-settings-package <pkg>:editable.rebuild=true`

The active build mode is recorded in `.venv/.xx_uv_incremental`; toggling the env var forces a
local C++ reinstall even if the version is unchanged.

`uv-sync` seeds the toolchain first (`scikit-build-core`, `setuptools-scm`, `cmake`, `ninja`,
`editables`). Unset (default): packages build in isolation normally — slower but hermetic.

---

## `constraints.txt` — reproducibility

**Do not `==`-pin `[project.dependencies]`** in published metadata. py10x-core is a library; exact
pins cause consumer conflicts and do not pin transitives anyway. Keep **ranges** in published
metadata.

`uv pip install` ignores `uv.lock` (only `uv sync` uses it), so on the pip-install flow `uv.lock` is
dead weight — it stays gitignored.

**Reproducibility = a committed `constraints.txt`**, applied via `uv pip install -c constraints.txt`
on **every** install (dev + all CI). `dev_10x/uv_sync.py` appends `-c` to every pip install;
`ci.yml` inherits it through `uv-sync`; `build.yml` and both cxx10x wheel workflows pass `-c`
explicitly.

### `xx-constraints`

```
xx-constraints compile              # conservative regen after pyproject edits (default)
xx-constraints compile --upgrade    # bump all pins to latest within ranges
xx-constraints check                # assert the active env is fully frozen
```

- **`compile`** runs `uv pip compile` over **all three** pyprojects (py10x + both siblings, paths
  from `[tool.dev_10x.siblings]`) with `--universal --all-extras --no-emit-package` for each sibling.
  Needs the `../cxx10x` checkout (`py10x-core-dev` mode). First-party packages are never pinned in the
  output (derived via `_first_party`: root `[project].name` + siblings + any `[tool.uv.workspace]`
  members — not a hardcoded list).
  - **Default (no `--upgrade`)**: conservative regen — keeps existing pins from `constraints.txt`
    wherever they still satisfy the ranges; only changes what a pyproject edit forces. Use after
    adding or changing a dependency.
  - **`--upgrade`**: re-resolves every pin to the latest version allowed by the ranges (ignores
    existing pins). Used by `refresh-constraints.yml` for the weekly bulk bump.
  - **`--python-version` = the project floor** (parsed from `requires-python`, e.g. `3.11`).
    `--universal` anchors its lower bound to the *target* Python, **not** to `requires-python`, so
    compiling under 3.12 silently drops every 3.11-only pin and its `; python_full_version < '3.12'`
    markers. Targeting the floor makes the freeze cover the full supported range regardless of the
    interpreter that runs the compile (dev or CI).
  - **`--custom-compile-command`** gives a stable, path-free header (`xx-constraints compile` or
    `xx-constraints compile --upgrade`); otherwise the absolute sibling paths leak into the
    autogenerated comment and churn the diff on every machine / runner.
- **`check`** asserts every *installed* third-party dist (minus the three first-party packages) is
  pinned in `constraints.txt`. Runs in `ci.yml`, `build.yml`, and both cxx10x workflows — the
  cross-repo enforcement point when a sibling adds a dep without a py10x regen.

**Known tradeoff:** for git-sibling profiles (`domain-dev`, `py10x-dev`) and cxx10x CI, a sibling
needing a version outside the pin hits a hard conflict → regenerate `constraints.txt` in
`py10x-core-dev` mode and commit.

dependabot keeps pins fresh — orthogonal to reproducibility (update vs freeze).

### `refresh-constraints.yml` — scheduled `xx-upgrade`

`.github/workflows/refresh-constraints.yml` automates the *update* side on a **weekly** cron
(Mon 04:00 UTC, plus `workflow_dispatch`) **without** eroding the freeze:

1. Sync `py10x-core-dev` (clones cxx10x `main` so all three pyprojects are present), then
   `xx-constraints compile --upgrade` against the latest compatible PyPI graph.
2. If `constraints.txt` is unchanged → stop (no tests, no PR).
3. If it changed → re-sync against the fresh pins (compile rewrites the file but does not
   reinstall), `xx-constraints check`, then the **full test suite** (MongoDB replica set +
   Playwright), mirroring `ci.yml`.
4. Only on green → open/update PR `chore: refresh constraints.txt` (only `constraints.txt`
   is committed). The PR is review-gated and merged by a human.

So `main` never auto-changes, the proposed freeze is green-by-construction, and a **red run is the
alert** that an upstream release broke us (do not merge — investigate the pin). Notes:

- A PR opened with the default `GITHUB_TOKEN` does **not** trigger `ci.yml` (GitHub blocks
  recursive workflow runs). Set repo secret **`CONSTRAINTS_PR_TOKEN`** (PAT/App token with
  Contents + PRs write) to also get the PR's own CI run; the workflow falls back to `GITHUB_TOKEN`
  when absent (the in-run suite is still the gate).
- Failure notifications follow GitHub's default scheduled-workflow rules (the cron's last editor);
  add an explicit Slack/issue step for team-wide alerting.

---

## CI release gates

### py10x `build.yml` (`test` → `publish`)

On **`pre/v*`** / **`prod/v*`** publish-trigger tag push:

1. Clone cxx10x.
2. Resolve each sibling tag via `python -m dev_10x.xx_ci latest_tag` (kernel-free — only
   `packaging` + `tomlkit`).
3. `uv pip install` siblings from the local clone at those tags (`git+file://…@<tag>`).
4. `uv pip install -e . --all-extras --requirements pyproject.toml -c constraints.txt`.
5. `xx_ci verify_sibling` for kernel and infra.
6. Full pytest suite, then publish.

### cxx10x `core_10x_wheels.yml` / `infra_10x_wheels.yml`

- `checkout fetch-depth: 0`.
- Clone py10x at the test-group-pinned `v{CORE_VER}` as a sibling.
- Install **kernel/infra editable first, then core** (core's pins admit them).
- Verify `py10x-core==CORE_VER` and both siblings are **editable** (PEP 610) else fail.
- Run py10x-core's full suite (replica-set tests auto-skip; no Mongo in cxx10x CI).

### CI gotchas

- After a coordinated `pre` or `prod` `--push`, `main` CI on **either** repo may start before the
  other finishes pushing its branch epilogues. Both workflows poll
  `xx_ci wait_sibling_branch_ready` before `uv-sync`: py10x waits on sibling repos; cxx10x passes
  `sync_base` so each attempt refreshes the py10x clone first.
- `uv pip install --all-extras` needs an explicit source:
  `-e . --all-extras --requirements pyproject.toml` (unlike `uv sync`).
- Tag triggers: **`pre/py10x-kernel-v*`** / **`prod/…`** (and core **`pre/v*`** / **`prod/v*`**).
- Never `==`-pin published `[project.dependencies]`.

---

## `xx_ci.py` — kernel-free CI shim

`core_10x/__init__.py` imports `py10x_kernel`, so **anything that imports `core_10x` needs the
compiled kernel.** Tag resolution and sibling verification in publish CI must run *before* siblings
are installed — hence `dev_10x/xx_ci.py` uses only `packaging` and `tomlkit`.

```
uv venv
uv pip install -c constraints.txt packaging tomlkit setuptools-scm
source .venv/bin/activate  # or .venv/Scripts/activate on Windows

python -m dev_10x.xx_ci latest_tag py10x-kernel
python -m dev_10x.xx_ci verify_sibling py10x-kernel
python -m dev_10x.xx_ci sibling_branch_ready main
python -m dev_10x.xx_ci wait_sibling_branch_ready main          # py10x CI
python -m dev_10x.xx_ci wait_sibling_branch_ready main sync_base  # cxx10x CI
```
