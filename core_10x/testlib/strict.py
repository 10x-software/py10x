"""Strict-mode test preconditions, shared across `core_10x` / `infra_10x` / `dev_10x` test suites.

`XX_TEST_STRICT=1` (read via `EnvVars.test_strict`) is set on py10x's *fully-provisioned* CI jobs
(`ci.yml` / `build.yml` / `refresh-constraints.yml`). There, a guard that *can't run* because a
provisioning precondition is unmet — git/uv missing, no source checkout, the cxx10x siblings absent,
or a non-replica-set Mongo (no transactions) — is a **defect to surface**, not something to skip
silently. So `need(...)` turns those skips into hard failures under strict.

Leave `XX_TEST_STRICT` UNSET everywhere else — local dev, and the cxx10x sibling wheel CI where
core-installed-as-a-wheel (no source pyproject) and no-Mongo make those skips legitimate.

Use this ONLY for *provisioning* preconditions. Genuinely-conditional skips (empty doc blocks, a
backend that owns a type, platform-specific cases) must stay plain `pytest.skip` — they should skip
even when fully provisioned.
"""
from __future__ import annotations

import pytest

from core_10x.environment_variables import EnvVars

def need(ok: bool, reason: str) -> None:
    """Require a provisioning precondition: skip when unmet, or FAIL under XX_TEST_STRICT."""
    if ok:
        return
    if EnvVars.test_strict:
        pytest.fail(f"XX_TEST_STRICT set but precondition unmet: {reason}")
    pytest.skip(reason)
