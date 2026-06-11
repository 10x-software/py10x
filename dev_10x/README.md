# `dev_10x` — developer tooling for the 10x packages

Three command-line tools (declared in `[project.scripts]`):

| command      | purpose                                                                 |
|--------------|-------------------------------------------------------------------------|
| `uv-sync`    | sync the venv against a chosen *dependency-source profile*              |
| `uv-run`     | run a single command under the last profile's source override          |
| `xx-promote` | cut release candidates / final releases and yank them                   |

## The three packages

They version **independently** and live in two git repos:

| package        | repo / path                | tags                         |
|----------------|----------------------------|------------------------------|
| `py10x-core`   | `py10x` (this repo)        | `vX.Y.Z` / `vX.Y.ZrcN`       |
| `py10x-kernel` | `cxx10x` / `core_10x`      | `py10x-kernel-vX.Y.Z[rcN]`   |
| `py10x-infra`  | `cxx10x` / `infra_10x`     | `py10x-infra-vX.Y.Z[rcN]`    |

py10x-core depends on the other two (forward). For testing, kernel/infra carry a *dev-only*
reverse dependency on py10x-core via a PEP 735 **`[dependency-groups]` `test`** group — which is
**not** published in wheel metadata, so the dependency cycle never reaches consumers.

---

## `xx-promote` — release promotion

Releases are not cut by hand-editing pins. `main` always carries **dev pins**; `xx-promote` tags
the repos and, for a final release, commits strict pins on a per-version release branch.

### Pin model (three places)

For a sibling whose next version is `T` (`N` = the next micro, `FLOOR` = its last released version):

- **`main` — dev pins ("Form A"):** `>=FLOOR,<=T,!=T,>=0.0.0.dev0`
  `<=T,!=T` admits every pre-release of `T` (`T.devN, TaN/bN, TrcN`) while dropping the `T` final
  (a plain `<T` would strip the pre-releases); `>=0.0.0.dev0` is a no-op bound that names a
  pre-release so uv **auto-enables** them for this package (no `--prerelease=allow`). The pin still
  **excludes** the `T` final and anything `>= N`. This lets a checkout (or a published rc) resolve
  to a sibling's dev/rc flaglessly while never silently adopting the next *final* release.
- **release branch — final-only pins:** `>=T,<N`
  No pre-release token, no auto-enable; admits only the `T` final and its post-releases.
- **reverse `test` group:** `py10x-core==<released core version>`.

> Why not one pin for everything? Whether uv auto-enables pre-releases is decided by the literal
> tokens in the specifier, so "dev-by-default but rc-when-released" cannot be a single static
> string — hence the explicit promotion step. Note also `>=Trc1,<T` is an **empty** set (`<T`
> excludes pre-releases of `T`); the tooling never emits it. "Latest tag" is always computed with
> `packaging.version.Version` (`max`), never `git --sort=-v:refname` / `sort -V`, which misorder
> pre-releases (`0.2.3` ranks *below* `0.2.3rc1`).

### Subcommands

`xx-promote` is a `core_10x.traitable_cli` tree: the command is a positional word and options are
`name=value` pairs.

```
xx-promote pre                            # cut the next rc for every package (tagging only)
xx-promote prod                           # promote each rc'd package to final
xx-promote yank pkg=<name> version=<ver>  # yank a tag (rc or final)
```

- **`pre`** computes each package's own target `T` and next rc number, then tags the repo's
  current `main` HEAD (`v{T}rc{n}`, `py10x-kernel-v{T}rc{n}`, `py10x-infra-v{T}rc{n}`). No pin
  changes — the Form A dev pins already admit the new rc.
- **`prod`** (per package that has an rc for its target):
  1. find the latest rc tag + commit;
  2. create the per-version release branch (`release/v{T}` / `release/py10x-{pkg}-v{T}`) off that
     commit;
  3. commit **final-only** pins there (py10x-core → siblings `>=T_sib,<N_sib`; kernel/infra →
     `test = ["py10x-core==T_core"]`) and tag the final on the branch;
  4. on `main`, re-floor py10x-core's Form A dev pins to the just-released sibling versions and
     point the reverse groups at the released core.

  Released code == rc code (the release commit only changes metadata), and the wheel built from the
  final tag carries the prod pins.
- **`yank`** renames the tag to `<tag>_yanked` (the build workflows ignore `*_yanked`, so the
  release is never rebuilt/republished) and **prints the manual PyPI yank instructions** — PyPI has
  no public yank API, so the index yank is a web action you perform yourself. Yanking a **final**
  also rolls `main`'s pins back to the latest non-yanked release; an rc yank is tag-rename only.

### Safety levels (every subcommand, as `name=value` flags)

| flag           | effect                                                                       |
|----------------|------------------------------------------------------------------------------|
| `dry_run=true` | print the full plan; change **nothing** (local or remote)                    |
| *(default)*    | apply **local** changes only — inspect with `git log`/`status`, reset to undo |
| `push=true`    | apply locally, then push to remotes **last**, only after all local steps pass |

`dry_run` always wins, so `dry_run=true push=true` previews what a push would do. Clean working
trees are required before any real change. `base=<path>` overrides the py10x repo root (default:
cwd). Always preview first:

```
xx-promote prod dry_run=true
xx-promote prod push=true
```

---

## `uv-sync` / `uv-run` — local source overrides

`uv-sync <profile> [uv args…]` transiently rewrites `[tool.uv.sources]` to point the three 10x
packages at a chosen source, runs `uv sync`, then **always reverts** `pyproject.toml` (it is never
left dirty) and records the profile in `.dev_10x_profile`.

| profile          | py10x-core      | py10x-kernel / py10x-infra |
|------------------|-----------------|----------------------------|
| `user`           | released wheel  | released wheels (index)    |
| `domain-dev`     | git `main`      | git `main`                 |
| `py10x-dev`      | local editable  | git `main`                 |
| `py10x-core-dev` | local editable  | local editable (`../cxx10x`)|

For local cxx packages it also passes `--reinstall-package` when the source's setuptools-scm
version changed.

`uv-run <command> [args…]` re-applies the **last** profile's override for the duration of a single
`uv run` (e.g. `uv-run pytest -q`) and reverts afterward — without re-seeding the venv.

### `XX_UV_INCREMENTAL=1`

When set **and** the active profile uses local-editable cxx packages, kernel/infra switch to
no-build-isolation incremental builds, so editing C++ in `../cxx10x` and re-running recompiles only
what changed (instead of a full isolated rebuild):

- `--no-build-isolation-package <pkg>` — build in the existing venv (reuse the persistent
  CMake/Ninja toolchain);
- `--config-settings-package <pkg>:build-dir=<venv>/cxx-build/<pkg>/{wheel_tag}` — a stable
  per-package build dir so incremental state persists across runs;
- `--config-settings-package <pkg>:editable.rebuild=true` — rebuild the extension at import time.

`uv-sync` first seeds the toolchain (`scikit-build-core`, `setuptools-scm`, `cmake`, `ninja`,
`editables`). Unset (the default), packages build in isolation normally — slower but hermetic.
