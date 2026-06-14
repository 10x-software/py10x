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
| `py10x-core`   | `py10x` (this repo)        | `v`                | `vX.Y.Z` / `vX.Y.ZrcN`       |
| `py10x-kernel` | `cxx10x` / `core_10x`      | `py10x-kernel-v`   | `py10x-kernel-vX.Y.Z[rcN]`   |
| `py10x-infra`  | `cxx10x` / `infra_10x`     | `py10x-infra-v`    | `py10x-infra-vX.Y.Z[rcN]`    |

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
- **Ordering:** always compare with `packaging.version.Version` (`max`), never
  `git --sort=-v:refname` / `sort -V` (they rank `0.2.3` *below* `0.2.3rc1`).

---

## `xx-promote` — release promotion

Releases are not cut by hand-editing pins. `main` always carries **dev pins**; `xx-promote` tags
the repos and, for a final release, commits strict pins on a per-version release branch.

`xx-promote` is a `core_10x.traitable_cli` tree: the command is a positional word and options use
the `--option value` form (dashes in names map to underscores, e.g. `--dry-run` → `dry_run`).
Boolean options also accept the `--option` / `--no-option` shortcuts (== `--option true` /
`--option false`). 

### Pin model (three places)

For a sibling whose next version is `T` (`N` = the next micro, `FLOOR` = its last released version):

- **`main` — dev pins ("Form A"):** `>=FLOOR,<=T,!=T,>=0.0.0.dev0`
  `<=T,!=T` admits every pre-release of `T` (`T.devN`, `TaN/bN`, `TrcN`) while dropping the `T` final
  (a plain `<T` would strip the pre-releases); `>=0.0.0.dev0` is a no-op bound that names a
  pre-release so uv **auto-enables** them for this package (no `--prerelease=allow`). The pin still
  **excludes** the `T` final and anything `>= N`.
- **release branch — final-only pins:** `>=T,<N`
  No pre-release token, no auto-enable; admits only the `T` final and its post-releases.
- **reverse `test` group:** `py10x-core==<released core version>`.

> Why not one pin for everything? Whether uv auto-enables pre-releases is decided by the literal
> tokens in the specifier, so "dev-by-default but rc-when-released" cannot be a single static
> string — hence the explicit promotion step. Note also `>=Trc1,<T` is an **empty** set (`<T`
> excludes pre-releases of `T`); the tooling never emits it.

### Subcommands

```
xx-promote pre                                # cut the next rc for every package (tagging only)
xx-promote prod                               # promote each rc'd package to final
xx-promote yank --pkg <name> --version <ver>  # yank a tag (rc or final)
```

- **`pre`** computes each package's own target `T` and next rc number, then tags the repo's
  current `main` HEAD (`v{T}rc{n}`, `py10x-kernel-v{T}rc{n}`, `py10x-infra-v{T}rc{n}`). A package
  is skipped when `git diff` shows no changes since its latest pre *or* prod tag across its
  release-relevant footprint (`GitHelpers.diff_pathspecs`): its source subtree **plus its publish
  workflow**, matched by the convention `.github/workflows/{subdir}*` (so `core_10x` →
  `core_10x_wheels.yml`). Siblings diff `core_10x`/`infra_10x` + that workflow glob, not the whole
  `cxx10x` repo; core's `.` already covers everything. A workflow edit changes how the package is
  built, so it must force a new rc. When the latest tag is an rc, `--push` can still publish it
  without minting a new rc. No pin changes — Form A dev pins already admit the new rc.
- **`prod`** (per package whose **latest** tag is a pre-release and that has an rc for its target):
  1. find the latest rc tag + commit;
  2. create the per-version release branch (`release/v{T}` / `release/py10x-{pkg}-v{T}`) off that
     commit;
  3. commit **final-only** pins there (py10x-core → siblings `>=T_sib,<N_sib`; kernel/infra →
     `test = ["py10x-core==T_core"]`) and tag the final on the branch;
  4. on `main`, re-floor py10x-core's Form A dev pins to the just-released sibling versions and
     point the reverse groups at the released core.

  Released code == rc code (the release commit only changes metadata), and the wheel built from the
  final tag carries the prod pins.
- **`yank`** renames the tag to `<tag>_yanked` (build workflows ignore `*_yanked`) and **prints
  manual PyPI yank instructions** — PyPI has no public yank API. Yanking a **final** also rolls
  `main`'s pins back to the latest non-yanked release; an rc yank is tag-rename only. There are
  intentionally **no** yank CI workflows.

### Safety levels (every subcommand, as `--option` flags)

| flag         | effect                                                                       |
|--------------|------------------------------------------------------------------------------|
| `--dry-run`  | print the full plan; change **nothing** (local or remote)                    |
| *(default)*  | apply **local** changes only — inspect with `git log`/`status`, reset to undo |
| `--push`     | apply locally, then push to remotes **last**, only after all local steps pass |

`dry_run` always wins. Clean working trees are required before any real change. `--base <path>`
overrides the py10x repo root (default: cwd). Always preview first:

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
   Index siblings are resolved in step 2; `--reinstall-package` forces a swap if currently editable/git.
2. **`uv pip install --requirements pyproject.toml`** (+ caller args such as `--all-extras`) —
   core's deps and extras, additive (keeps step-1 siblings). Form A dev pins admit in-dev siblings.
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
xx-constraints compile    # regenerate constraints.txt (default)
xx-constraints check      # assert the active env is fully frozen
```

- **`compile`** runs `uv pip compile` over **all three** pyprojects (py10x + both siblings, paths
  from `[tool.dev_10x.siblings]`) with `--universal --all-extras --no-emit-package` for each sibling.
  Needs the `../cxx10x` checkout (`py10x-core-dev` mode). First-party packages are never pinned in the
  output (derived via `_first_party`: root `[project].name` + siblings + any `[tool.uv.workspace]`
  members — not a hardcoded list).
  - **`--python-version` = the project floor** (parsed from `requires-python`, e.g. `3.11`).
    `--universal` anchors its lower bound to the *target* Python, **not** to `requires-python`, so
    compiling under 3.12 silently drops every 3.11-only pin and its `; python_full_version < '3.12'`
    markers. Targeting the floor makes the freeze cover the full supported range regardless of the
    interpreter that runs the compile (dev or CI).
  - **`--custom-compile-command 'xx-constraints compile'`** gives a stable, path-free header;
    otherwise the absolute sibling paths leak into the autogenerated comment and churn the diff on
    every machine / runner.
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
   `xx-constraints compile` against the latest compatible PyPI graph.
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

On tag push (`v*`, excluding `*_yanked`):

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

- `uv pip install --all-extras` needs an explicit source:
  `-e . --all-extras --requirements pyproject.toml` (unlike `uv sync`).
- Tag triggers exclude `*_yanked`.
- Never `==`-pin published `[project.dependencies]`.

---

## `xx_ci.py` — kernel-free CI shim

`core_10x/__init__.py` imports `py10x_kernel`, so **anything that imports `core_10x` needs the
compiled kernel.** Tag resolution and sibling verification in publish CI must run *before* siblings
are installed — hence `dev_10x/xx_ci.py` uses only `packaging` and `tomlkit`.

```
python -m dev_10x.xx_ci latest_tag py10x-kernel
python -m dev_10x.xx_ci verify_sibling py10x-kernel
```
