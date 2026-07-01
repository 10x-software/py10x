# RC / release promotion — design note

**Status:** proposed, not yet implemented. Extends the current `xx-promote` model
(`dev_10x/README.md` → "`xx-promote`"). Supersedes the per-version `release/v{T}` sketch this note
started from (see *Alternatives considered*).

## Goal

1. External consumers get **coordinated release candidates** the same way they get coordinated
   finals — exact sibling versions baked into the published wheel, not range-resolved.
2. The **RC workflow *is* the PROD workflow** — one routine, so promoting to final is fully
   dress-rehearsed at every rc.

## Staging

Built in two stages; the fragile / heavy mechanisms (pin-only detection, multi-writer concurrency)
all fall in stage 2. Sections below marked *(stage 2)* belong there.

**Stage 1 — reproducible, coordinated RC installs.** Same feature *surface* as today (cut rc,
promote, yank, status); the one change is that rc wheels carry exact `==` sibling pins (and reverse
`>=`) like finals, so an external `pip install …rc1` resolves the coordinated set. Internals do
change: rc moves onto the tool-owned `pre` branch, a **declarative pure planner** (decisions from
current tags + pins), and **atomic-push crash recovery** — each command pushes once per repo with
`git push --atomic`, so the remote is never half-updated; recovery is `resync` (force local refs to
origin) + idempotent re-run, *not* in-place reconcile. `--from=main` only; **yank latest only**;
**serialize by discipline** ("one release at a time"), so no lock. No pin-only detection or
`mark-merged` is needed (`pre` holds only tool-generated pin commits).

**Stage 2 — release patching + concurrency.** `--from=release` maintenance and the marker /
`mark-merged` / pin-only apparatus it requires; yank `--cascade` + scope inference; and true
multi-writer concurrency if ever needed (tag-as-mutex — see *Risks*; **not** the earlier CAS /
`reconcile()` design, which atomic-push recovery supersedes).

## Branches

Releases live on **tool-owned, protected branches that track current state**; **tags are the
historical record**. Per package, two branches:

- `pre` — HEAD is the current release candidate (latest rc commit).
- `prod` — HEAD is the current release (latest final commit).

Because `cxx10x` hosts two independently-versioned packages, the branches are **per package**:

| repo     | branches                                                                 |
|----------|--------------------------------------------------------------------------|
| `py10x`  | `pre`, `prod`                                                            |
| `cxx10x` | `pre/py10x-kernel`, `prod/py10x-kernel`, `pre/py10x-infra`, `prod/py10x-infra` |

Six tool-owned branches total. Properties:

- **Protected against humans; force-updatable by `xx-promote`** (a bypass actor / app token).
  Consecutive rcs cut from `main` don't fast-forward, so the tool **force-resets** these pointers —
  which is semantically correct for a "current candidate/release" pointer (the candidate genuinely
  rebased onto newer `main`).
- **No per-version branches → nothing to prune.** A version is a *tag*; the two branches only ever
  point at the *current* rc/final.
- **Candidate fixes arrive via PR into `pre`/`prod`** (reviewed), then a promote re-pins + tags. So
  protection restores a human-review gate for release-line fixes, even though the promote commit
  itself is tool-written.

### What `git log pre`/`prod` shows

Because the branches are force-reset on each `--from=main` re-cut, `git log pre` shows the **current
candidate's lineage + all of `main` beneath it** — *not* a ledger of past releases. `--from=release`
accumulates commits within the live candidate; the next `--from=main` collapses them. **Past
releases are reachable only via their tags** (`git tag -l`, `git log <tag>`) — the conventional
outcome (cf. Go modules, setuptools-scm). So `pre`/`prod` are *current-state pointers*, not a
release history. (An append-only `releases` branch merged-on-promote would give a linear ledger, but
adds a merge per release for what tags already provide — rejected.)

## Model

One routine, parameterized by *flavor* (`pre`/`prod`) and *base* (`--from main|release`):

```
_promote(flavor, from):
    gate    : verify run-from branch + reachability         (see "Guard")
    safety  : refuse if the target branch has un-tagged-only commits, unless --force (show diff)
    base    : main HEAD             (pre --from=main)
              pre HEAD              (pre --from=release  — iterate the candidate)
              latest rc (pre HEAD)  (prod               — stack the final on the rc)
    commit  : write the coordinated pins on `base` -> C
    dev_tag : tag `main` HEAD with `{T}rc(N+1).dev` when cutting rcN (setuptools-scm marker on `main`)
    update  : force-reset (--from=main, prod) or fast-forward (--from=release) the target branch -> C
    tag     : C   (v{T}rcN for pre, v{T} for prod)
    push    : tags + updated branch, remotes last
```

| command                        | run from (gate)            | base               | branch updated        | tag             |
|--------------------------------|----------------------------|--------------------|-----------------------|-----------------|
| `pre --from=main` *(default)*  | `main` reachable from HEAD | `main` HEAD        | `pre` (force-reset)   | `v{T}rcN`       |
| `pre --from=release`           | `pre`                      | `pre` HEAD         | `pre` (fast-forward)  | `v{T}rcN`       |
| `prod --from=release` *(def.)* | `prod`                     | latest rc (`pre`)  | `prod` (force-update) | `v{T}`          |

- `prod --from=main` is **rejected** — every final must come from an rc (full dress rehearsal).
- `prod` stacks the final-pin commit on the latest rc, so **released source == rc source** (only the
  pin rewrite differs).
- **Single invocation orchestrates both repos** (siblings first, then core).

### Batch formation is declarative (idempotent / resumable)

Re-cut decisions compare **persistent state** (tags + current pins), never an in-process diff, so a
run is idempotent and a partial failure just **resumes**:

- **sibling:** re-cut iff its own footprint changed since its last tag.
- **core:** re-cut iff its own footprint changed **or** its current pin lags the **latest sibling
  tag**.

Two properties fall out: a **dangling `==` pin is impossible** (core only ever pins to a sibling tag
that already exists — so siblings must be tagged before core), and the "sibling moved ⇒ core re-cut"
trigger is just "pin ≠ latest tag," needing no separate footprint rule. (This is why a sibling
re-cut forces a *dependent-package* re-cut — earlier drafts mis-wrote "dependent core".) The
footprint diff is **scoped via `diff_pathspecs`** and is the *same* code path used by `--diff-only`.

### Crash recovery: atomic pushes + `resync` (supersedes reconcile-from-tags / CAS)

Tags are the only authoritative state; `pre`/`prod` are derived (`pre` = commit of the latest rc tag,
`prod` = commit of the latest non-yanked final tag; `main` floor = epilogue pins from the latest
non-yanked released versions). But rather than *repairing* derived refs in place after a crash, the
tool keeps the **remote consistent** so recovery is trivial:

- **Atomic push.** Each command applies all local mutations, then pushes **once per repo with
  `git push --atomic`** (branch force-updates, release tags, dev-marker drop+create, `main` —
  all-or-nothing), then **isolated publish-trigger pushes** (one refspec per `git push`). CI listens
  on the triggers, not release tags.
- **Refuse-until-synced.** `require_synced` refuses the next run while local ≠ remote (committed
  and pushed: `main`/managed-tags match `origin`), so you never build on an un-synced state.
- **`resync` + idempotent re-run.** Recovery is `xx-promote resync` — force each repo's
  `main`/`pre`/`prod` branches and managed tags back to `origin`, discarding local-only work — then
  re-run, which the **declarative planner** resumes from current tags. Cross-repo partial push
  (siblings pushed, core not) surfaces as **one** un-synced repo; `resync` it and the re-run re-cuts
  core to coordinate.
- **`--publish-only`.** Creates publish triggers for the latest releases that lack one (non-force
  `git tag`). Idempotent — a re-run when triggers already exist exits successfully with no git
  mutations.

This **retires the earlier reconcile-first + CAS / `--force-with-lease` design**: with atomic
per-repo pushes the inconsistent-remote states it repaired are unreachable, and cross-repo atomicity
(impossible with two remotes) is unnecessary because the run is idempotent. Concurrency stays
"one release at a time" (Stage 1); a true multi-writer story, if ever needed, is the tag-as-mutex
note in *Risks*, not a shared `reconcile()` loop.

## Guard (reachability)

`--from` is a *declared expectation* the tool verifies against your ancestry — it never checks out a
named base branch:

- **`--from=main`:** `main` tip is an ancestor of HEAD (`git merge-base --is-ancestor main HEAD`).
  Forces you to be at/ahead of `main` (can't cut from stale `main`). New version from global tag
  state (next micro, next rc#).
- **`--from=release`:** run from `pre`/`prod`, whose HEAD `xx-promote` maintains as the latest
  rc/final. The most-recent tag reachable from HEAD must be the line's current rc (for `pre`
  iterate / `prod` promote). A stale candidate (reachable tag ≠ globally-latest rc) is rejected —
  this is how old candidates retire.

### Destructive-reset safety *(stage 2)*

> Only relevant once `pre` can carry human commits (via `--from=release`). In stage 1 `pre` holds
> only tool-generated pin commits, so a `--from=main` re-fork has nothing to protect.

A `--from=main` re-fork abandons the whole candidate line, so **all** of `pre`'s un-tagged commits
are discarded unless they're on `main`. The guard makes that cherry-pick discipline **tracked and
gated** — not cryptographically enforced; advancing the marker ultimately trusts the operator — via a
**movable `*-merged` marker ref** per package per kind (`pre-merged-{pkg}`, `prod-merged-{pkg}` — six
total, pushable):

- The marker points at the latest commit confirmed **forward-ported to `main`**. The reset is
  **allowed iff `<marker>..<branch>` is all pin-only** (regenerated anyway); a non-pin commit in that
  range **blocks** it.
- `mark-merged [<commit>]` force-advances the marker after a real forward-port — an **acknowledgment
  recorded in git**, replacing a blunt `--force`. A `--from=main` re-fork resets the marker to the
  new `pre` HEAD (all-from-main).
- **"Pin-only" is decided by reverse-derivation** (robust to formatting drift): parse the commit's
  actual diff into pin transitions, render the canonical message, and compare to the stamped header
  (`promote: kernel:1.2.3rc1->1.2.3;infra:…`). Anything in the diff that *doesn't* reduce to a pin
  transition is the "unexpected" residue → block / review. This *interprets* the diff rather than
  reproducing it, so it doesn't depend on byte-exact tomlkit output (the earlier "derive expected
  diff from header, assert equal" direction was fragile to formatting).
- `git cherry main pre` (patch-id) is at most an **advisory hint** in `xx-promote diff` ("looks
  already-merged"), *not* an auto-advance — patch-id has false negatives (a fix hand-applied or
  reimplemented differently in `main` won't match). The authoritative signal is explicit
  `mark-merged`.
- `xx-promote diff` **shows** what's in `<marker>..<branch>` (`--full-diff` to expand). `--discard`
  is the deliberate "drop un-ported work on purpose" escape hatch (rare). `prod` force-update carries
  the same guard against `prod-merged-{pkg}`.

## Branch structure

Diagram for `py10x`; `cxx10x` mirrors it per package with reverse `test` pins instead of forward
deps. `==X / ==Y` are core's forward pins on `kernel` / `infra`.

```
snapshot after cutting v1.3.0rc2 and promoting v1.3.0

main  ●──●──●──●──●──●──●──●      rc-window pins (pre epilogue + post-prod re-floor)
                       │
                       └──●  ← pre     forked from main HEAD; rc pin commit
                          │     tag v1.3.0rc2 · core deps ==1.4.0rc2 / ==0.9.0rc2
                          │
                          └──●  ← prod    final pin stacked on the rc
                                tag v1.3.0 · core deps ==1.4.0 / ==0.9.0

tag-only (no branch):  v1.3.0rc1   ← superseded candidate; the next `pre --from=main`
                                     force-reset `pre` away from it (preserved only by its tag)
```

Candidate fix without `main`'s drift: PR the fix into `pre` (off its current rc HEAD), then
`pre --from=release` fast-forwards `pre` and tags `v1.3.0rc3`.

## Pin matrix

| where                         | forward (core → siblings)                 | reverse (sibling `test` group → core, **dev-only, unpublished**) |
|-------------------------------|-------------------------------------------|-------------------------------------------------------------------|
| **`pre` / `prod`** (rc/final) | exact `==` coordinated version            | `>=` coordinated version of the core promoted in the same batch   |
| **`main` (after `pre`)**       | rc-window `>=rcN,<rc(N+1)` per sibling    | `>=` latest released core                                         |
| **`main` (after `prod`)**      | post-final window `>=T,<{next_micro}rc1` | `>=` latest released core                                         |

- **Published pins exact; unpublished CI pins floored.** Forward `==` is the external coordination
  guarantee. Reverse `>=` only selects which core cxx10x CI tests a sibling against.
- The reverse floor's **prerelease token falls out for free**: `>=Tc_rcN` admits core prereleases
  (rc tests the prerelease line); `>=Tc` admits only finals (final tests the released line).
- If a package is unchanged in a batch, it is **not re-cut**; its forward/reverse pins floor to
  core's **latest final** (the "unchanged sibling" rule).
- *Rc-window pins on `main`* complement the setuptools-scm **`.dev` markers** on cxx10x `main`
  (`{T}rc(N+1).dev` after `pre`, `{next_micro}rc0.dev` after `prod`). The window exclusive upper
  (`<rc(N+1)` / `<{next_micro}rc1`) and the marker rc line **must stay in lockstep** — both are
  derived from the same helpers (`rc_window_exclusive_upper`, `main_dev_marker_tag`, etc.) and
  guarded in `test_xx_utils.py`.
- The rc-window **inclusive rc floor** auto-enables prereleases. It
  **blocks** a published `rc(N+1)` on the index while py10x `main` still pins the `rcN` line (issue
  **A**), and with `uv-sync` step 1 (`-e` + pin on the same command) surfaces a **lagged** cxx10x
  checkout (`rcN.dev0` below the floor) as a resolve failure rather than a silent index pull
  (issue **B** — guarded by a real-uv test in `test_xx_tooling_guards.py`).
- **Post-prod window** `>=T,<{next_micro}rc1` — **not** `>=T,<next_micro>` — admits the post-final
  marker editable and blocks the next publishable rc and the `{next_micro}` final.

## `pre` + `prod` epilogues on `main`

After each coordinated **`pre` cut**, py10x-core's `main` epilogue writes **rc-window** pins
(`>=rcN,<rc(N+1)`) for every sibling from the batch's coordinated versions (including unchanged
siblings at a final, which get the **post-final window** shape). After **`prod`**, the epilogue
writes **post-final window** pins (`>=T,<{next_micro}rc1`) and repoints sibling reverse `test` groups
at the released core. Main epilogue pin-only commits are **excluded from core footprint** so a
second `pre` with no source changes does not re-cut.

## Tooling / flags

- `--dry-run` — print the plan, change nothing (existing).
- `--diff-only` — read-only: show the **content diff of the about-to-be-cut release vs the latest
  released final** ("what's new for users"). Short by default; `--full-diff` expands. Distinct from
  `--dry-run`, which shows *actions* rather than the release delta.
- `xx-promote diff` / `mark-merged` — review what's on `pre` not yet forward-ported to `main`, and
  advance the `*-merged` marker to acknowledge a forward-port (see *Destructive-reset safety*).
- `--discard` — deliberate override to drop un-forward-ported commits without acknowledging them
  (rare; replaces a blunt `--force`).
- `--push` — apply locally, then push **tags + the updated `pre`/`prod` branch** to remotes, last
  (existing; already pushes tags).

## Yank / revert

`yank` reverts a release: it rolls the `pre`/`prod` pointers back (a destructive force-update — same
`--force` guard), renames the tags to `*_yanked`, deletes the matching **`pre/`/`prod/` publish
trigger**, rolls back py10x-core **`main` forward pins** to match the latest non-yanked release tags
(rc-window or post-final window as appropriate), and prints **manual PyPI yank instructions** only
when the version is already on the index (PyPI has no public yank API). Decisions:

- **Only a *core* release is yankable**; doing so yanks the **batch's members** — core plus the
  siblings whose pin **changed since the previous core release** (inferred from the pyproject diff;
  unchanged siblings are left alone).
- **Cascade:** yanking a version yanks everything after it. Only the **latest** release yanks without
  `--cascade`; an older one requires `--cascade` (which also sweeps orphaned intermediate sibling
  rcs).
- **Version numbers are consumed, not freed.** PyPI forbids re-uploading a yanked version, so
  generation must floor on `max(all tags incl. yanked)`; *selection* still excludes `*_yanked`
  and `*.dev` main markers. Two different maxes — distinct from today's single yanked-excluded
  ordering.

(Command name kept as `yank` — the PEP 592 / distribution term — even though it's implemented as a
repo-state revert.)

## Conscious tradeoffs

- **Exact `==` on first-party deps in published metadata** — against the "never `==`-pin" rule,
  carved out *only* for the co-released family. Holds while no third party depends on kernel/infra
  independently; the guardrail is rescoped to **third-party** deps.
- **`==T` excludes `.postN`** (`SpecifierSet("==1.4.0").contains("1.4.0.post1")` is `False`), so the
  forward pin is **stricter than today's `final_pin` (`>=T,<next_micro`, which admits posts)**.
  Consequence: a metadata-only sibling `.postN` is *not* picked up by an already-published core wheel
  — it propagates only via a core **re-cut** (declaratively triggered once the `.post` is tagged,
  since core's pin then lags the latest sibling tag). Intended: this closes a coordination hole the
  range leaves open (a consumer resolving `1.4.0.post1` against a core tested on `1.4.0`). Do **not**
  widen the pin to admit posts — that reopens the untested-artifact hole.
- Released **source** == rc source, but the final commit is `rc-commit + metadata-diff`, not the rc
  commit itself.
- A new sibling rc **forces a re-cut of the dependent package** (core), to refresh its exact pin —
  the price of exact coordination (handled by declarative reconciliation, above).
- Reverse `>=` has **no upper cap**, but is **self-correcting**: a *final* sibling floors to a
  *final* core (`>=Tc`, no prerelease token), and the forward `==` acts as a consistency check — if
  `>=` admits a too-new core, that core's `kernel==` won't match the sibling under test, so the
  resolver backtracks to the coordinated core. Relies on the sibling being installed **editable /
  version-pinned** (cxx10x CI already verifies this) and on the resolver *backtracking* rather than
  hard-erroring — both covered by an assumption-guard test.
- cxx10x CI must resolve "**max core tag satisfying the spec**" instead of extracting one `==`
  version (`dev_10x/xx_ci.py`, still kernel-free).
- **`pre`/`prod` are tool-force-updated protected branches** — needs bypass config for the bot;
  humans contribute only via PR into them.
- **`pre`/`prod` are current-state pointers, not history** — past releases are tag-only.
- **`cxx10x` carries per-package `pre`/`prod`** (independent versioning), so "two branches" is six
  total across the repos.

## Risks & open questions

Resolved by decisions above (recorded so the hardening is implemented + tested):

- **Pin-edge propagation / no dangling pin** → declarative reconciliation (siblings tagged before
  core; core re-cuts when its pin lags the latest sibling tag).
- **Cross-repo partial failure** → siblings-first ordering + idempotent resume; e2e test injects a
  mid-batch failure and asserts no dangling pin.
- **setuptools-scm correctness** → assumption-guard test: tag on the committed-pin HEAD with a clean,
  non-shallow tree stamps the tag version; dirty/shallow variants assert the dev fallback.
- **Yank** → core-only, batch-member scope by pyproject diff, cascade with `--cascade`,
  consumed-version-number generation, epilogue revert.
- **Reverse `>=` drift** → self-correcting via forward `==` + editable sibling (assumption-guard
  test).
- **Stale / un-pushed base** → `local == origin` precondition: `local main` must match `origin/main`.
- **Pre-only commit loss** → enforced cherry-pick discipline (`diff` / `mark-merged`, pin-only
  auto-discard, patch-id auto-clear).

- **Crash / partial failure (single + cross-repo)** → **atomic per-repo push** keeps the remote
  consistent (never half-updated); `require_synced` refuses an un-synced start; recovery is `resync`
  (local refs := origin) + idempotent re-run. Cross-repo (siblings pushed, core not) is one un-synced
  repo + a resuming re-run — no joint atomicity needed. **This supersedes the earlier reconcile-first
  + CAS / `--force-with-lease` design** (see *Crash recovery* above); e2e injects a mid-push failure
  and asserts resync + resume.
- **Concurrency (Stage 1)** → **serialize by discipline** ("one release at a time"). No lock, no CAS.
  If true multi-writer ever matters, the lever is **tag-as-mutex** (create the version's tag — or
  `v…_yanked` for yank — *first*; it's the atomic claim, the rest derives from it and is resumable);
  a release-level lock is the simpler-but-deadlock-prone fallback. Not built; not needed for rare
  releases.

## Future

- **SemVer-aware bumping (defer to `1.0.0`):** make `--from=main` bump the *minor* (`1.2.x → 1.3.0`)
  and `--from=release` bump the *micro* (`1.2.x → 1.2.(x+1)`), so the two paths produce structurally
  distinct versions. Until then both compute next-micro; the latest-tag rule prevents an actual
  collision (you only ever operate off the latest tag, and a duplicate tag just fails).

## Testing strategy

A pyramid mirroring the existing pure-helpers / CLI-routing split. Local repos only; `--push` is
covered by one bare-remote test.

- **Plan-level, exhaustive (in-memory).** Structure `_promote` to compute a **plan** (branch / base /
  pins / tags / guard pass-fail) *purely*, separate from execution, then parametrize the planner
  across the real combinatorial space — flavor × `--from` × changed/unchanged package set ×
  rc-iterate vs first-rc × guard/force states — and assert the plan. Extend the `test_xx_utils.py`
  style; add PEP 440 assumption guards for the new exact-`==` forward and `>=` reverse pin forms.
- **Execution, representative (real git, `tmp_path`).** New `test_xx_promote_e2e.py` with **2 repos /
  3 packages** (a `py10x` repo and a `cxx10x` repo holding `core_10x`/`infra_10x` with the right tag
  prefixes). One scenario per *structure*: coordinated `pre --from=main`, `pre --from=release`
  iterate, `prod` promote, guard rejection, destructive-reset `--force`. Assert real git state
  (branch HEADs, tags, commit parentage, pyproject pins at the tag).
- **`--push`, one bare-remote test.** `git init --bare` a pair of local "remotes" as `origin`;
  verify tags land, `pre`/`prod` update (incl. force-reset), no stray branches pushed, and remotes
  are touched **last**.
- CLI routing + safety-flag tests stay in `test_xx_promote.py` (extend for `--from`, `--diff-only`,
  `--force`).

## Rationale / alternatives considered

The skeleton is conventional: **GitFlow-style release branches** (here just two tool-owned `pre`/
`prod` lines), setuptools-scm tagging, and **coordinated batch releases**. The last is a hybrid, not
pure independent versioning: packages keep **independent version numbers** (core `v1.3.0` while
kernel `v1.4.0`) and an unchanged package is skipped — but a release is a **coordinated batch**, cut
together and cross-pinned, not each package shipping on its own schedule. So it sits between Lerna's
*fixed* mode (one shared version) and *independent* mode (no coordination). The unusual parts all
trace to one constraint — coordinating a **tightly-coupled family across two repos with exact
reproducibility for external rc consumers**.

- **Ranges + lockfile/constraints (mainstream default).** What we already do with `constraints.txt`.
  Rejected as *insufficient*: constraints.txt only protects consumers who use it (our CI); it does
  **not** give an external `pip install core==X.Yrc1` the coordinated siblings. This design extends
  that guarantee to the published rc wheel. **If the only consumer of rc wheels is ever our own
  constraints-pinned CI, this design is not worth its cost** — ranges + constraints give ~90% of the
  benefit for far less machinery.
- **Monorepo (changesets / Nx).** Would make coordination nearly free, but the C++/Python split keeps
  us in two repos for unrelated reasons.
- **semantic-release / release-please.** Orthogonal — single-package version/changelog automation;
  doesn't address coordination, would layer on top rather than replace this.
- **Per-version `release/v{T}` branches (superseded).** The note's first sketch gave every candidate
  its own branch. Replaced by the two tool-owned `pre`/`prod` pointers: bounded (no proliferation,
  nothing to prune) and conventional (a minimal two-line release-branch model).
- **Transient / tag-only commits (rejected).** Create a branch only for a command's duration, leaving
  release commits reachable solely via tags. Coherent ("release = tag" is mainstream) and it
  dissolves pruning, but it puts the release commit on *no* branch — breaking `git log <branch>`,
  branch protection, and discoverability. `pre`/`prod` recover all of that for the current release
  while keeping tags as history.

## Doc / guardrail changes implied

- `AGENTS.md` §7 and `dev_10x/README.md` "constraints" — rescope "never `==`-pin" to **third-party**
  deps; state first-party siblings are `==`-pinned on `pre`/`prod`.
- `dev_10x/README.md` "Pin model" / "Subcommands" — document `pre`/`prod` branches, `--from`, the
  reachability guard, `--diff-only`, and the destructive-reset `--force`; rc/final live on `pre`/
  `prod` with exact pins.
- **Repo config:** branch protection + bot bypass on `pre`/`prod` (per package in `cxx10x`).
- Tests as in *Testing strategy*.
