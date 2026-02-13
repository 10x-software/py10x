# Open Source & Intellectual Property Checklist

This document helps you prepare the `py10x-core` project for open-source release and avoid unintentional IP infringement. It is not legal advice; consider review by your legal counsel before publishing.

---

## 1. Current state (as of this checklist)

| Item | Status | Notes |
|------|--------|--------|
| **Project license** | MIT | `LICENSE` file present; copyright Copyright 2025-2026 10X CONCEPTS LLC |
| **Copyright in source** | Root only | No file-level copyright headers in `.py` files. Optional to add (see below). |
| **Third-party code** | None found | No "Based on", "From", "Source:", or vendored copies detected in repo. |
| **NOTICE / THIRD_PARTY** | Optional | `NOTICE` in repo root if used for third-party attribution. |

---

## 2. Third-party Python dependencies (MIT compatibility)

All direct dependencies in `pyproject.toml` are commonly used under permissive licenses that are compatible with distributing your project under MIT. You should still **verify** licenses (e.g. with a tool or manually) before release.

| Dependency | Typical license | MIT compatible |
|------------|-----------------|----------------|
| importlib-resources | Apache 2.0 | Yes |
| numpy | BSD-3-Clause | Yes |
| python-dateutil | Apache 2.0 / BSD | Yes |
| cryptography | Apache 2.0 / BSD | Yes |
| pymongo | Apache 2.0 | Yes |
| typing-extensions | PSF | Yes |
| scipy | BSD-3-Clause | Yes |
| keyring | MIT | Yes |
| requests | Apache 2.0 | Yes |
| hatchling | MIT | Yes |
| hatch-build-scripts | (check) | (verify) |
| Optional: PyQt6 / Rio / pytest / ruff / etc. | GPL / MIT / BSD etc. | PyQt6 is GPL/Commercial – see §4 |

**Recommended:** Before release, run a dependency license checker and fix or document any exceptions:

```bash
uv run licensecheck
# Or: pip install licensecheck && licensecheck
```

Add any **attribution or notice** required by your dependencies to a `NOTICE` or `THIRD_PARTY_LICENSES` file (see §5).

### licensecheck results (summary)

Running `licensecheck` in this project reports:

- **Compatible (✔):** All third-party open-source dependencies (e.g. cryptography, pymongo, numpy, scipy, requests, importlib-resources, keyring, typing-extensions, etc.) are MIT-compatible (Apache 2.0, BSD, MIT, MPL 2.0, PSF, ISC).
- **Flagged (✖), expected and documented:**
  - **hatchling** — License sometimes reported empty by licensecheck; hatchling is MIT-licensed. If you run licensecheck in CI, allow-list hatchling so the check does not fail on this known exception; see the tool’s docs for ignore/allow-list options.

---

## 3. Your own code and contributions

- **Ownership:** Confirm that all code in the repo is either (a) written by 10x (or contractors with appropriate assignments) or (b) used under a compatible license with correct attribution.
- **No copied code:** Do not paste in code from Stack Overflow, blogs, or other projects without verifying license and adding attribution where required.
- **Contributors:** If you accept external contributions, use a process that makes license and IP clear (e.g., “Contributions under the same license as the project” or a CLA). See CONTRIBUTING.md and optionally a DCO/CLA.

---

## 4. Trademarks, logos, and assets

- **Names:** “py10x-core”, “10x”, “10x Software”, "10x Platform" – ensure you have rights to use these and that open-source use does not conflict with your trademark policy. Consider a short TRADEMARKS section in README or docs.
- **Images:** `10x-jerboa-in-desert.jpeg`, `10x-jerboa.jpeg` – both are **AI-generated**. Confirm the generator’s terms allow use in this project (and attribution if required); document in README or NOTICE if needed. To identify which tool was used, see “How to check which AI tool was used” below.
- **Third-party logos:** If the repo or docs use logos of other products (e.g. MongoDB, Python), use them in line with their trademark guidelines.

**How to check which AI tool was used (for AI-generated images):**

1. **Metadata (EXIF / XMP):** Many JPEGs store creator or software in metadata. From the project root, run:
   - **exiftool** (install with `brew install exiftool`):  
     `exiftool 10x-jerboa.jpeg 10x-jerboa-in-desert.jpeg`  
     Look for fields like `Creator`, `Software`, `XMP:CreatorTool`, `XMP:History`, or similar.
   - **Python (Pillow):**  
     `pip install Pillow` then:
     ```python
     from PIL import Image
     img = Image.open("10x-jerboa.jpeg")
     print(img.info)  # general info
     if getattr(img, "getexif", None):
         exif = img.getexif()
         if exif: print(dict(exif))
     ```
     Some tools write the generator name in `info` or in XMP (Pillow may not show all XMP; exiftool is more complete).

2. **If metadata is empty or stripped:** Many AI tools do not embed their name, or it is lost when re-saving. Then the only way to know is your own records (where you generated the images) or the site/app you downloaded them from. If you are unsure, state in NOTICE that the images are AI-generated and that use is subject to the applicable generator’s terms (as already noted).

**Checked for this project:** exiftool was run on `10x-jerboa.jpeg` and `10x-jerboa-in-desert.jpeg`. Metadata contains only technical fields (dimensions 1024×1536, JFIF, resolution, encoding); no Creator/Software/XMP fields identify the AI generator. The NOTICE’s generic wording (“AI-generated; use and attribution subject to the generator’s terms”) therefore applies.

---

## 5. NOTICE and attribution

- **LICENSE:** Keep the root MIT `LICENSE` as-is.
- **NOTICE (optional but good practice):** Create a `NOTICE` file in the repo root if you need to:
  - Preserve copyright notices for your project.
  - Satisfy attribution requirements from dependencies (e.g. Apache 2.0 “NOTICE”).
- **THIRD_PARTY_LICENSES** (when do you need it?):
  - **Usually not required** for a library that only *declares* dependencies (like `py10x-core`): users install your package and pip/uv installs dependencies from PyPI; each dependency ships its own license. A `NOTICE` file with third-party attributions (names, copyright, project URLs) is typically enough to satisfy Apache 2.0–style “give credit” requirements.
  - **Consider or required** when: you **vendor or bundle** third-party source inside your repo or distribution; you ship a **combined binary or application** that includes third-party code; or a dependency’s license explicitly requires “include a copy of this license” in *distributed works* and you are distributing a combined work (e.g. static linking, bundled app). In those cases, add a `THIRD_PARTY_LICENSES` file or `docs/licenses/` with the full license texts; some teams generate this from `pip`/`uv` output.

---

## 6. Optional: file-level copyright headers

No legal requirement for MIT, but some organizations add a short notice to each source file:

```python
# SPDX-License-Identifier: MIT
# Copyright (c) 2025-2026 10X CONCEPTS LLC
```

You can do this only for new files, or add project-wide via a one-time script and then enforce in CONTRIBUTING.

---

## 7. Pre-release checklist (summary)

Before publishing the repo as open source:

- [x] Run a **dependency license audit** and add any required attributions (§2, §5).
- [x] Confirm **no in-bound code** is used without proper license/attribution (§3).
- [x] Confirm **trademarks and assets** (logos, images) are cleared for public use (§4).
- [x] Add **NOTICE** (and if needed **THIRD_PARTY_LICENSES**) (§5).
- [ ] Optionally add **SPDX/copyright** to key or all source files (§6).
- [x] Update **README** as needed (no requirement to state license or internal dependencies).
- [x] Consider a short **SECURITY.md** and **CONTRIBUTING.md** (you already have these; ensure they mention license and IP for contributors where appropriate).

---

## 8. Ongoing

- Run a **license check** in CI (e.g. `licensecheck` or similar) to catch new dependencies that are not MIT-compatible or need attribution.
- When adding dependencies, **check license and notice requirements** before merging.
- Keep **NOTICE** (and **THIRD_PARTY_LICENSES** if you use one) updated when dependencies change.

---

*This checklist is a living document. Update it as the project’s structure or licensing changes.*
