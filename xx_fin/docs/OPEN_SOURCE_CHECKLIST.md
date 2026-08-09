# Open Source & Intellectual Property Checklist — xx_fin (py10x-fin-base / py10x-fin-base-cxx)

This document tracks `xx_fin/`'s readiness for its Phase 1 publish rehearsal (per
`../../py10x/docs/xxfin_move_plan.md`) — the first package published out of this domain, ahead of
its later relocation into the already-public `py10x` monorepo. It follows the same structure as
`py10x/docs/OPEN_SOURCE_IP_CHECKLIST.md`. Not legal advice; consider legal review before publishing.

---

## 1. Current state

| Item | Status | Notes |
|------|--------|--------|
| **Project license** | MIT | `xx_fin/LICENSE`; copyright `2025-2026 10X CONCEPTS LLC, XXFIN LLC and contributors` |
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
| aadc | **Proprietary/commercial** (not open source) | N/A — not distributed under an OSI license | Installable freely from PyPI (separate install, not bundled); ships a time-limited trial license, continued/production use requires a MatLogica license key. Listed in `xx_fin/NOTICE`'s commercial-dependencies section; macOS-availability detail lives in `README.md`. Excluded on macOS (`sys_platform != 'darwin'`) per `xx_fin/pyproject.toml` because MatLogica doesn't publish an aadc build for that platform — not because it's optional there. |
| xbbg (optional `bbg` extra) | Apache 2.0 | Yes | Open source; listed in `xx_fin/NOTICE`'s open-source section. |
| blpapi (optional `bbg` extra) | **Proprietary/commercial** (not open source) | N/A — not distributed under an OSI license | Bloomberg's own API, distributed only via Bloomberg's dedicated, entitlement-gated package index (`[[tool.uv.index]] name = "bloomberg"` in the domain root `pyproject.toml`); requires a valid Bloomberg entitlement/Terminal license. Listed in `xx_fin/NOTICE`'s commercial-dependencies section, not alongside xbbg. |

**Recommended before release:** run `licensecheck` (or equivalent) against `xx_fin`'s resolved
dependency tree, as `py10x-core` does, and treat `aadc`'s and `blpapi`'s commercial-license
requirements as documented exceptions (§5) rather than failures.

---

## 3. Own code and contributions

- **Ownership:** all code under `xx_fin/` is written by 10X / contractors with appropriate
  assignments; no code pasted in from Stack Overflow/blogs/other projects without attribution.
- **Contributors:** external contributions, once accepted, are under the same MIT license as the
  rest of the project (see the domain-wide `CONTRIBUTING.md` once `xx_fin/` relocates to `py10x`).

---

## 4. Trademarks, logos, and assets

- **Names:** `xxfin`, `cxxfin`, `py10x-fin-base`, `py10x-fin-base-cxx` — same trademark posture as
  `py10x-core`; no separate action needed here.
- **No images/logos** are shipped under `xx_fin/`.

---

## 5. NOTICE and attribution

- `xx_fin/LICENSE` — MIT, copyright `10X CONCEPTS LLC, XXFIN LLC and contributors`.
- `xx_fin/NOTICE` — open-source third-party attribution (QuantLib, xbbg) plus a separate section
  disclosing `aadc` and `blpapi` as commercial/proprietary dependencies requiring their own license.
- `README.md` ("Optional JIT acceleration via AADC") — implementation detail on `aadc` (the
  `use_cxxfin`/`aadc_license` settings, why it's excluded on macOS); the licensing fact itself lives
  in NOTICE.
- `THIRD_PARTY_LICENSES` — not needed: `xx_fin` only *declares* dependencies (no vendored/bundled
  third-party source, no combined binary distribution), same reasoning as `py10x-core`.

---

## 6. Publish plumbing

| Item | Status | Notes |
|------|--------|--------|
| Publish workflow | Done | Single `.github/workflows/finbase_wheel.yml`, triggered by one tag `py10x-fin-base-v*`. Builds `py10x-fin-base-cxx` wheels (cibuildwheel, 3 OSes) and the `py10x-fin-base` sdist/wheel in parallel jobs, then publishes both to PyPI in one `publish` job — trusted PyPI publishing (OIDC, no tokens). |
| Version coordination | Done | `xx_fin/cxxfin/pyproject.toml`'s `setuptools_scm` and `xx_fin/pyproject.toml`'s `hatch-vcs` both derive their version from the *same* tag pattern (`py10x-fin-base-v*`), so a release tag always gives both packages the identical version string. The `build_finbase` job resolves that shared version via `hatch version` and patches `py10x-fin-base-cxx` to an exact `==<version>` pin before building — a manual stand-in for the `write_forward_pins` tooling planned for Phase 2 of the move plan. |
| Upstream deps publishable | Done | `py10x-core`, `py10x-kernel`, `py10x-infra`, `aadc` already on public PyPI; `cxx10x` headers repo already public on GitHub (needed for `cxxfin`'s CMake `FetchContent`). |
| Prerelease-chain pins | Done, needs future automation | `py10x-core`'s only *final* PyPI release (`0.2.2`) pins `py10x-kernel`/`-infra` to a range with no prerelease-flavored bound, so plain `pip`/`uv` resolution silently falls back to the old final `py10x-kernel==0.2.0` instead of the current `0.2.1rcNN` line. Fixed by pinning `py10x-core` in `xx_fin/pyproject.toml` and `py10x-kernel` in `xx_fin/cxxfin/pyproject.toml`'s `[build-system]` the same way the domain root `pyproject.toml` already does (`>=0.0.0.dev0`/`>=0.0.0rc0` markers, PEP 440), rather than a blanket `--pre` in CI. **TODO:** these are hand-maintained pins, correct only while `py10x-core`/`py10x-kernel` remain prerelease-only past their last final — needs the Phase 2 `write_forward_pins` promote automation (move plan) to keep them current instead of manual edits. |

---

## 7. Pre-release checklist (summary)

- [x] LICENSE with correct copyright (§1).
- [x] NOTICE with third-party attribution, incl. the `aadc` and `blpapi` commercial-license
  disclosures (§2, §5).
- [x] Confirm no in-bound/vendored code without attribution (§3).
- [x] Confirm trademarks/assets cleared (§4) — none applicable.
- [x] Pure-Python `py10x-fin-base` publish workflow added (§6).
- [ ] Cut `py10x-fin-base-cxx` + `py10x-fin-base` rc tags; confirm both workflows build and publish.
- [ ] Clean-venv smoke test: `pip install py10x-fin-base` → `import xxfin; import cxxfin`.
- [x] Dependency license check (§2): `quantlib-python` confirmed BSD 3-Clause (PyPI metadata), `xbbg`
  confirmed Apache-2.0 (its own `pyproject.toml` — PyPI's classifier field was empty). Both
  MIT-compatible; matches `NOTICE`.

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

- Run a license check in CI when adding new dependencies under `xx_fin/`.
- Keep NOTICE updated as `xx_fin`'s direct third-party dependencies change.
- Re-run the pre-release checklist above ahead of each Phase 1 rc tag until Phase 3 relocation.

---

*This checklist is a living document. Update it as `xx_fin`'s structure, dependencies, or licensing
change, and again once it relocates into `py10x/xx_fin/`.*
