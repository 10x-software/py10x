# Open Source & Intellectual Property Checklist — xx_fin (py10x-fin-base / py10x-fin-base-cxx)

This document tracks licensing / IP readiness for the published packages under `xx_fin/`
(`py10x-fin-base` and `py10x-fin-base-cxx`) in the `py10x` monorepo. It follows the same
structure as [`docs/OPEN_SOURCE_IP_CHECKLIST.md`](../../docs/OPEN_SOURCE_IP_CHECKLIST.md).
Not legal advice; consider legal review before publishing.

(Historical extract/relocate notes: [`docs/attic/xxfin_move_plan.md`](../../docs/attic/xxfin_move_plan.md).)

---

## 1. Current state

| Item | Status | Notes |
|------|--------|--------|
| **Project license** | MIT | `xx_fin/LICENSE` and `xx_fin/cxxfin/LICENSE` (same text); copyright `2025-2026 10X CONCEPTS LLC, XXFIN LLC and contributors`. Separate LICENSE under `cxxfin/` so the published `py10x-fin-base-cxx` wheel ships a license file (same pattern as `py10x-kernel` / `py10x-infra`). |
| **pyproject metadata** | Done | `xx_fin/pyproject.toml` and `xx_fin/cxxfin/pyproject.toml` already declare `license = {text = "MIT"}`, `authors = [{name = "10X CONCEPTS LLC", email = "py10x@10x-software.org"}]` |
| **Copyright in source** | Root only | No file-level copyright headers in `.py`/`.cpp`/`.h` files, matching the `py10x-core` precedent (optional, not added). |
| **Third-party code** | None found | No vendored/copied third-party source under `xx_fin/`; `cxxfin/CMakeLists.txt` pulls `cxx10x` headers via `FetchContent` from the public `github.com/10x-software/cxx10x`, not a vendored copy. |
| **NOTICE** | Done | `xx_fin/NOTICE` covers `xx_fin`'s own direct third-party deps not already in `py10x-core`'s NOTICE — open source (QuantLib, xbbg) and commercial (aadc, blpapi) in separate sections. |
| **Secrets** | Clean | Full-history grep of `git log -p --all -- xx_fin/` found no credentials; only 4 commits touch the path. |

---

## 2. Third-party Python dependencies

| Dependency | Typical license | MIT compatible | Notes |
|------------|-----------------|-----------------|-------|
| py10x-core, py10x-kernel, py10x-infra | MIT | Yes | Already public on PyPI. |
| quantlib-python | BSD-3-Clause-style (QuantLib License) | Yes | |
| aadc | **Proprietary/commercial** (not open source) | N/A — not distributed under an OSI license | Installable freely from PyPI (separate install, not bundled); ships a time-limited trial license, continued/production use requires a MatLogica license key. Listed in `xx_fin/NOTICE`'s commercial-dependencies section; platform-availability detail lives in `README.md`. Excluded on macOS and on Windows+Python 3.13 per `xx_fin/pyproject.toml` because MatLogica doesn't publish an aadc wheel for those targets — not because it's optional there. |
| xbbg (optional `bbg` extra) | Apache 2.0 | Yes | Open source; listed in `xx_fin/NOTICE`'s open-source section. |
| blpapi (optional `bbg` extra) | **Proprietary/commercial** (not open source) | N/A — not distributed under an OSI license | Bloomberg's own API, distributed only via Bloomberg's dedicated, entitlement-gated package index (`[[tool.uv.index]] name = "bloomberg"` in `xx_fin/pyproject.toml`); requires a valid Bloomberg entitlement/Terminal license. Listed in `xx_fin/NOTICE`'s commercial-dependencies section, not alongside xbbg. |

**Recommended before release:** run `licensecheck` against `xx_fin`'s resolved dependency tree
**including optional extras** (default `licensecheck` only resolves main dependencies). Same
command shape as the core checklist
([`docs/OPEN_SOURCE_IP_CHECKLIST.md`](../../docs/OPEN_SOURCE_IP_CHECKLIST.md) §2):

```bash
# From the py10x repo root:
uv run --no-sync licensecheck -r xx_fin/pyproject.toml --extras bbg,dev
```

Treat `aadc`'s and `blpapi`'s commercial-license requirements as documented exceptions (§5)
rather than failures.

### licensecheck results (summary)

Command (re-run before each release):

```bash
uv run --no-sync licensecheck -r xx_fin/pyproject.toml --extras bbg,dev
```

**Last run:** 2026-08-10 (macOS / Python 3.11 venv) — **92** compatible, **3** flagged.

- **Compatible (✔):** Including `quantlib` / `quantlib-python` (BSD), `xbbg` (Apache-2.0 via
  `bbg`), `hatchling`, `py10x-kernel` / `py10x-infra`, and `dev` tooling transitives.
- **Flagged (✖), expected and documented:**
  - **blpapi** (`bbg` extra) — `OTHER_PROPRIETARY LICENSE`; listed in `NOTICE` commercial section.
  - **cxxfin**, **`..`** — local path / workspace resolution noise; `cxxfin` is MIT
    (`xx_fin/cxxfin/LICENSE`), not a third-party issue.
- **Not in this run:** **aadc** — environment marker excludes it on macOS (also excluded on
  Windows + Python 3.13). Still a documented MatLogica commercial dependency in `NOTICE` wherever
  it installs; expect it to appear as proprietary if you re-run on Linux/Windows where the marker
  allows install.

---

## 3. Own code and contributions

Same policy as the root checklist
([`docs/OPEN_SOURCE_IP_CHECKLIST.md`](../../docs/OPEN_SOURCE_IP_CHECKLIST.md) §3) — ownership and
contributor terms are project-wide, not per-package. Verified for `xx_fin/`: no code pasted in
from Stack Overflow/blogs/other projects without attribution.

---

## 4. Trademarks, logos, and assets

Same posture as the root checklist
([`docs/OPEN_SOURCE_IP_CHECKLIST.md`](../../docs/OPEN_SOURCE_IP_CHECKLIST.md) §4) — `xxfin`,
`cxxfin`, `py10x-fin-base`, `py10x-fin-base-cxx` need no separate trademark action. No
images/logos are shipped under `xx_fin/`.

---

## 5. NOTICE and attribution

- `xx_fin/LICENSE` and `xx_fin/cxxfin/LICENSE` — MIT, copyright
  `10X CONCEPTS LLC, XXFIN LLC and contributors` (keep both in sync).
- `xx_fin/NOTICE` — open-source third-party attribution (QuantLib, xbbg) plus a separate section
  disclosing `aadc` and `blpapi` as commercial/proprietary dependencies requiring their own license.
- `README.md` ("Optional JIT acceleration via AADC") — implementation detail on `aadc` (the
  `use_cxxfin`/`aadc_license` settings, platform exclusions); the licensing fact itself lives
  in NOTICE.
- `THIRD_PARTY_LICENSES` — not needed, per the root checklist's reasoning
  ([`docs/OPEN_SOURCE_IP_CHECKLIST.md`](../../docs/OPEN_SOURCE_IP_CHECKLIST.md) §5): `xx_fin` only
  *declares* dependencies, no vendored/bundled third-party source or combined binary distribution.

---

## 6. Publish plumbing

| Item | Status | Notes |
|------|--------|--------|
| Publish workflow | Done | Single `.github/workflows/finbase_wheel.yml`, triggered by one tag `py10x-fin-base-v*`. Builds `py10x-fin-base-cxx` wheels (cibuildwheel, 3 OSes) and the `py10x-fin-base` sdist/wheel in parallel jobs, then publishes both to PyPI in one `publish` job — trusted PyPI publishing (OIDC, no tokens). |
| Version coordination | Done | `xx_fin/cxxfin/pyproject.toml`'s `setuptools_scm` and `xx_fin/pyproject.toml`'s `hatch-vcs` both derive their version from the *same* tag pattern (`py10x-fin-base-v*`), so a release tag always gives both packages the identical version string. Co-release `{name}-cxx==` pins are written by `xx-promote`; the publish workflow validates the committed pin against the tagged version. |
| Upstream deps publishable | Done | `py10x-core`, `py10x-kernel`, `py10x-infra`, `aadc` already on public PyPI; `cxx10x` headers repo already public on GitHub (needed for `cxxfin`'s CMake `FetchContent`). |
| Prerelease-chain pins | Done for 0.3.0 | Core `0.3.0rc1` is on PyPI with rc-window sibling pins. A **0.3.0 final** of core/kernel/infra closes the old `0.2.2` gap (final core could resolve an old final kernel). Keep `xx_fin`/`cxxfin` pins promote-managed. |

---

## 7. Pre-release checklist (summary)

- [x] LICENSE with correct copyright for **both** `py10x-fin-base` and `py10x-fin-base-cxx`
  (`xx_fin/LICENSE`, `xx_fin/cxxfin/LICENSE`) (§1).
- [x] NOTICE with third-party attribution, incl. the `aadc` and `blpapi` commercial-license
  disclosures (§2, §5).
- [x] Confirm no in-bound/vendored code without attribution (§3).
- [x] Confirm trademarks/assets cleared (§4) — none applicable.
- [x] Pure-Python `py10x-fin-base` publish workflow added (§6).
- [x] Cut `py10x-fin-base` (+ cxx) rc tags; workflows build and publish (`finbase_wheel.yml`).
- [x] Clean-venv smoke test: install from build artifacts → `import xxfin; import cxxfin`
  (CI `smoke_test` job).
- [x] Dependency license check with optional extras (§2):
  `uv run --no-sync licensecheck -r xx_fin/pyproject.toml --extras bbg,dev` —
  `quantlib-python` / `xbbg` MIT-compatible; `blpapi` / `aadc` documented commercial exceptions.

Known, accepted-risk items — explicit calls for the `0.1rc1` pre-release, not oversights:

- Placeholder/"TO BE FIXED" market-convention data in `xxfin/dev_data_helpers/ir_rate_mkt_conventions_create.py`
  (TONA/ESTR/SARON) — still present as of `0.1rc1`. Accepted as fine for a pre-release; revisit before
  a non-`rc` release.
- `manual_tests/` is excluded from the **wheel** (`[tool.hatch.build.targets.wheel] exclude`) but still
  ships in the **sdist** (hatchling's sdist target has no matching exclude). Reviewed: nothing secret
  in `manual_tests/`, so shipping it in the sdist is accepted as fine.

Known, intentionally out-of-scope items tracked elsewhere (not blocking this checklist):

- Domain repo root (`xxfin_commod`, `xxfin_positions`, `xxfin_testing`, root `pyproject.toml`'s
  proprietary license) — out of scope; stays private, doesn't ship in the `py10x-fin-base` wheel.

---

## 8. Ongoing

- Run a license check when adding dependencies under `xx_fin/` — include optional extras:
  `uv run --no-sync licensecheck -r xx_fin/pyproject.toml --extras bbg,dev`.
- Keep NOTICE updated as `xx_fin`'s direct third-party dependencies change.
- Keep this checklist aligned with the core
  [`docs/OPEN_SOURCE_IP_CHECKLIST.md`](../../docs/OPEN_SOURCE_IP_CHECKLIST.md) when the
  licensecheck command shape or exception-handling guidance changes.
- Re-run the pre-release checklist above ahead of each fin-base rc / final tag.

---

*This checklist is a living document. Update it as `xx_fin`'s structure, dependencies, or licensing
change.*
