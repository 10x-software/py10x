# syntax=docker/dockerfile:1
# Two independent targets, both defaulting to the functional-account entrypoint
# (see docker/entrypoint.sh, core_10x/functional_account_keyring.py).
#
#   dev        Builds this exact checkout together with its C++ siblings from source (the same
#              `dev_10x.uv_sync py10x-core-dev --all-extras` command ci-test-suite uses, with
#              XX_UV_INSTALL_MODE=normal -- see dev_10x/README.md) -- NOT from PyPI: kernel/infra's
#              *published* versions may not satisfy the pin currently in pyproject.toml (a normal
#              state mid-development, not an error), and a PR that coordinates core + cxx10x
#              changes together needs its own sibling source, not a stale release. Requires an
#              extra build context named `cxx10x` (a checkout of 10x-software/cxx10x at the
#              matching branch/tag -- see .github/workflows/ci.yml for how callers supply it). The
#              venv is created fresh *inside* this build (`uv venv` here, not copied in from the
#              host) so it's fully self-contained -- a host-built .venv copied in via `COPY`
#              breaks: its bin/python symlink points at the *host's* absolute interpreter path,
#              which doesn't exist in this image. Built by CI right after the test suite, and by
#              the PR-time functional-account-e2e job to verify unreleased changes for real.
#              Siblings install non-editable ('normal' mode) -- /cxx10x is only needed *during*
#              the build, not afterward (still copied into this stage for now; dropping it via a
#              multi-stage split is a deferred follow-up, not done yet).
#
#   production Plain `pip`-equivalent install of a *released* py10x-core version from PyPI --
#              no repo checkout baked in at all. What actually ships; default target for a bare
#              `docker build .`.
FROM python:3.12-slim AS base

RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

# Generic placeholder account. docker/entrypoint.sh renames it to the pod's functional-account
# identity (FUNCTIONAL_ACCOUNT_ID) at container start, since VaultUser.myname() reads the real
# OS username with no override hook -- identity has to be real before any Python runs.
RUN useradd --create-home --shell /usr/sbin/nologin appuser

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# ---- dev: build this checkout + its C++ siblings from source (CI-only; not a portable artifact) --
FROM base AS dev
# git: hatch-vcs shells out to `git describe` for py10x-core's version, and uv_sync reads
# `git remote get-url origin`; production doesn't need it (installs an already-versioned release).
# libpq5: psycopg (infra_10x/postgres_store.py) loads it at import time via ctypes; there's no
# psycopg[binary]/[c] extra pinned, so the plain package needs the system client library present.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git cmake ninja-build build-essential libpq5 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . /app
# `/cxx10x` must sit next to `/app` (i.e. resolve as `/app/../cxx10x`) -- [tool.dev_10x.siblings]
# in pyproject.toml declares sibling paths relative to the py10x repo root, same as a real
# `../cxx10x` local checkout.
COPY --from=cxx10x . /cxx10x

RUN uv venv

# XX_UV_INSTALL_MODE=normal (dev_10x/README.md): plain, non-editable install of py10x-kernel/
# py10x-infra -- no persistent build-dir, no rebuild-on-import (unlike 'incremental' mode, which
# exists for iterating on C++ source locally, not for a build-once image). py10x-core itself is
# unaffected by this setting and always installs editable (uv_sync forces it -- see
# dev_10x/uv_sync.py's INSTALL_MODES docstring), which is why /app (not /cxx10x) still needs to
# be present and writable at runtime below.
ENV XX_UV_INSTALL_MODE=normal
RUN --mount=type=cache,target=/root/.cache/uv \
    . .venv/bin/activate \
    && python -m dev_10x.uv_sync py10x-core-dev --all-extras

# pytest writes its own .pytest_cache under rootdir (/app) by default; the container runs as the
# renamed functional account (non-root, entrypoint.sh's gosu step), so /app needs to be writable
# by it. `usermod -l` only renames the login, so chowning to the placeholder account's uid here
# still matches after the rename. /cxx10x doesn't need this: 'normal' mode never touches it again
# after this build step.
RUN chown -R appuser:appuser /app

ENV PATH="/app/.venv/bin:${PATH}"
CMD ["python", "-m", "pytest", "core_10x/unit_tests/test_functional_account_vault.py", "-v"]

# ---- production: pip-equivalent install of a released version from PyPI -----------------------
FROM base AS production
ARG PY10X_CORE_VERSION
COPY constraints.txt /tmp/constraints.txt
# Retry + --refresh: the CI step that waits for this version to be resolvable on PyPI runs on the
# runner's native network, while this RUN executes inside BuildKit's own network namespace -- the
# two can land on different PyPI/Fastly CDN edges, so a release that already passed the outer wait
# can still 404 here for a few seconds until propagation catches up on *this* path too (seen for
# real: the outer check succeeded in <1s, this install 404'd 16s later on py10x-core==0.3.2rc2).
# --refresh-package matters because /root/.cache/uv is a BuildKit cache mount that persists
# *across* builds -- without it, a retry could keep re-serving the same stale cached index
# response instead of actually re-checking PyPI on each attempt. Scoped to just the first-party
# siblings (the only packages a release build could hit mid-propagation for) rather than a blanket
# --refresh, which would also needlessly revalidate every other pin in constraints.txt.
RUN --mount=type=cache,target=/root/.cache/uv \
    test -n "$PY10X_CORE_VERSION" \
    && ok= \
    && for i in 1 2 3 4 5 6; do \
         uv pip install --refresh-package py10x-core --refresh-package py10x-kernel --refresh-package py10x-infra \
           --system -c /tmp/constraints.txt "py10x-core==${PY10X_CORE_VERSION}" && { ok=1; break; }; \
         echo "py10x-core==${PY10X_CORE_VERSION} not yet resolvable here (attempt $i/6); retrying in 15s..." >&2; \
         sleep 15; \
       done \
    && [ -n "$ok" ] \
    && rm /tmp/constraints.txt

CMD ["python", "-c", "import core_10x; print('py10x-core', core_10x.__version__, 'ready')"]
