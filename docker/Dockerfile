# syntax=docker/dockerfile:1
# Two independent targets, both defaulting to the functional-account entrypoint
# (see docker/entrypoint.sh, core_10x/functional_account_keyring.py).
#
#   dev        Builds this exact checkout together with its C++ siblings from source (the same
#              `dev_10x.uv_sync py10x-core-dev --all-extras` command ci-test-suite uses) -- NOT
#              from PyPI: kernel/infra's *published* versions may not satisfy the pin currently
#              in pyproject.toml (a normal state mid-development, not an error), and a PR that
#              coordinates core + cxx10x changes together needs its own sibling source, not a
#              stale release. Requires an extra build context named `cxx10x` (a checkout of
#              10x-software/cxx10x at the matching branch/tag -- see .github/workflows/ci.yml for
#              how callers supply it). The venv is created fresh *inside* this build (`uv venv`
#              here, not copied in from the host) so it's fully self-contained -- a host-built
#              .venv copied in via `COPY` breaks: its bin/python symlink points at the *host's*
#              absolute interpreter path, which doesn't exist in this image. Built by CI right
#              after the test suite, and by the PR-time functional-account-e2e job to verify
#              unreleased changes for real. Siblings install editable (`-e`, matching uv_sync's
#              own incremental-build config), so /cxx10x must stay present in the final image,
#              not just the build stage -- it's not a build-only intermediate.
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

# XX_UV_INCREMENTAL=1: scikit-build-core keeps its cmake/ninja build state in
# .venv/py10x-build/<pkg>/<config>/... (dev_10x/README.md's "XX_UV_INCREMENTAL=1" section). That
# directory must land in the *regular* image layer, not a --mount=type=cache: the editable
# kernel/infra installs re-validate (and, if the build dir looks stale/incomplete, `cmake --build`)
# on every *import*, not just at build time -- so whatever's baked into the shipped image at
# .venv/py10x-build has to be the real, fully-configured CMake build directory the editable finder
# expects, and a cache mount's contents never make it into the image layer (only ~/.cache/uv,
# which just holds downloaded wheels, is safe to cache-mount here). Rebuilds are still avoided
# across separate `docker build` runs via ordinary layer caching (cache-from/cache-to: type=gha
# on the build-push-action steps that build this target) -- as long as this step's inputs
# (this checkout's source, /cxx10x's content) are unchanged, BuildKit skips re-running it entirely.
ENV XX_UV_INCREMENTAL=1
RUN --mount=type=cache,target=/root/.cache/uv \
    . .venv/bin/activate \
    && python -m dev_10x.uv_sync py10x-core-dev --all-extras

# The editable kernel/infra installs re-check (and, if stale, rebuild into .venv/py10x-build) on
# *every* import, not just at build time -- editable.rebuild=true is baked into the installed
# finder, not something a runtime env var can turn off. The container runs as the renamed
# functional account (non-root, entrypoint.sh's gosu step), so /app must be writable by it;
# `usermod -l` only renames the login, so chowning to the placeholder account's uid here still
# matches after the rename.
RUN chown -R appuser:appuser /app /cxx10x

ENV PATH="/app/.venv/bin:${PATH}"
CMD ["python", "-m", "pytest", "core_10x/unit_tests/test_functional_account_vault.py", "-v"]

# ---- production: pip-equivalent install of a released version from PyPI -----------------------
FROM base AS production
ARG PY10X_CORE_VERSION
COPY constraints.txt /tmp/constraints.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    test -n "$PY10X_CORE_VERSION" \
    && uv pip install --system -c /tmp/constraints.txt "py10x-core==${PY10X_CORE_VERSION}" \
    && rm /tmp/constraints.txt

CMD ["python", "-c", "import core_10x; print('py10x-core', core_10x.__version__, 'ready')"]
