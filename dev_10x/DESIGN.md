# `dev_10x` release model — design rationale

Why the release-promotion tooling in [`dev_10x/README.md`](README.md) looks the way it does, and
what is deliberately not built yet. Split out from the README so the README can stay a reference
(what to run, what each piece does) while this stays the "why," read only when the design itself
is in question.

## Design rationale

The release model is conventional GitFlow-style tooling (`pre`/`prod` branches, setuptools-scm
tagging) plus **coordinated batch releases** across two repos. Packages keep independent version
numbers (core `v1.3.0` while kernel `v1.4.0`) and unchanged packages are skipped — but a release is a
**coordinated batch**, cut together and cross-pinned, not each package shipping on its own schedule.
It sits between Lerna's *fixed* mode (one shared version) and *independent* mode (no coordination).
The unusual parts trace to one constraint: coordinating a **tightly-coupled family across two repos
with exact reproducibility for external rc consumers**.

### Alternatives considered

- **Ranges + lockfile/constraints (mainstream default).** What we already do with `constraints.txt`.
  Rejected as *insufficient*: `constraints.txt` only protects consumers who use it (our CI); it does
  **not** give an external `pip install core==X.Yrc1` the coordinated siblings. This design extends
  that guarantee to the published rc wheel. **If the only consumer of rc wheels is ever our own
  constraints-pinned CI, this design is not worth its cost** — ranges + constraints give ~90% of the
  benefit for far less machinery.
- **Monorepo (changesets / Nx).** Would make coordination nearly free, but the C++/Python split keeps
  us in two repos for unrelated reasons.
- **semantic-release / release-please.** Orthogonal — single-package version/changelog automation;
  doesn't address coordination, would layer on top rather than replace this.
- **Per-version `release/v{T}` branches (superseded).** Replaced by the two tool-owned `pre`/`prod`
  pointers: bounded (no proliferation, nothing to prune) and conventional.
- **Transient / tag-only commits (rejected).** Puts the release commit on *no* branch — breaking
  `git log <branch>`, branch protection, and discoverability. `pre`/`prod` recover all of that for the
  current release while keeping tags as history.

### Conscious tradeoffs

- **Exact `==` on first-party deps in published metadata** — carved out *only* for the co-released
  family. The guardrail is rescoped to **third-party** deps (see [constraints](README.md#constraintstxt--reproducibility)).
- **`==T` excludes `.postN`** (`SpecifierSet("==1.4.0").contains("1.4.0.post1")` is `False`), so the
  forward pin is **stricter than `>=T,<next_micro`** (which admits posts). A metadata-only sibling
  `.postN` is *not* picked up by an already-published core wheel — it propagates only via a core
  **re-cut** (declaratively triggered once the `.post` is tagged). Do **not** widen the pin to admit
  posts — that reopens an untested-artifact hole.
- Released **source** == rc source, but the final commit is `rc-commit + pin rewrite`, not the rc
  commit itself.
- A new sibling rc **forces a core re-cut** to refresh its exact pin — the price of exact coordination.
- Reverse `>=` has **no upper cap**, but is **self-correcting** via the forward `==` and editable
  sibling installs (cxx10x CI verifies PEP 610 editable).
- **`pre`/`prod` are tool-force-updated protected branches** — humans contribute via PR into them;
  the promote commit itself is tool-written.
- **`pre`/`prod` are current-state pointers, not history** — past releases are tag-only. Because
  branches force-reset on each `--from=main` re-cut, `git log pre` shows the current candidate's
  lineage plus `main` beneath it, not a ledger of past releases.

## Stage 2 (not implemented)

Stage 1 (shipped) covers coordinated rc/final cuts with `--from=main` only, yank-latest-only, and
serialize-by-discipline ("one release at a time"). Stage 2 would add release-line maintenance and
heavier concurrency controls:

- **`pre --from=release`** — iterate a live candidate (fast-forward `pre` from `pre` HEAD) instead of
  re-forking from `main`.
- **`mark-merged` / `*-merged` marker refs** — gate destructive `--from=main` re-forks when `pre`
  carries human commits: reset allowed only when `<marker>..<branch>` is pin-only; `mark-merged`
  acknowledges forward-ports to `main`.
- **`xx-promote diff` / `--diff-only`** — show un-forward-ported work on `pre`/`prod` vs `main`.
- **Yank `--cascade`** — yank older releases and sweep orphaned intermediate sibling rcs (Stage 1
  refuses yanking anything but the latest without `--cascade`, which is not implemented).
- **Multi-writer concurrency** — tag-as-mutex if ever needed; Stage 1 relies on discipline only.
- **SemVer-aware bumping (defer to `1.0.0`)** — `--from=main` bumps *minor*, `--from=release` bumps
  *micro*, so the two paths produce structurally distinct versions.
