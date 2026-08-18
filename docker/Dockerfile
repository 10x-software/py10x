# syntax=docker/dockerfile:1
# Two independent targets, both defaulting to the functional-account entrypoint
# (see docker/entrypoint.sh, core_10x/functional_account_keyring.py):
#
#   dev        Reuses a build context that already has a prepared repo + .venv (whatever
#              `python -m dev_10x.uv_sync py10x-core-dev --all-extras` produced for that commit —
#              real cxx10x kernel/infra, test deps, this exact source tree). Built by CI right
#              after the test suite already built that same .venv, and by the PR-time
#              functional-account-e2e job to verify unreleased changes for real. Never built
#              standalone from a clean checkout -- there is no .venv to reuse.
#
#   production Plain `pip`-equivalent install of a *released* py10x-core version from PyPI via
#              `uv pip install --system` -- no repo checkout, no C++ build. What actually ships;
#              default target for a bare `docker build .`.
FROM python:3.12-slim AS base

RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

# Generic placeholder account. docker/entrypoint.sh renames it to the pod's functional-account
# identity (FUNCTIONAL_ACCOUNT_ID) at container start, since VaultUser.myname() reads the real
# OS username with no override hook -- identity has to be real before any Python runs.
RUN useradd --create-home --shell /usr/sbin/nologin appuser

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# ---- dev: reuse an already-prepared checkout + .venv (CI-only; not a standalone build) --------
FROM base AS dev
WORKDIR /app
COPY . /app
ENV PATH="/app/.venv/bin:${PATH}"
CMD ["python", "-m", "pytest", "core_10x/unit_tests/test_functional_account_vault.py", "-v"]

# ---- production: pip-equivalent install of a released version from PyPI -----------------------
FROM base AS production
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ARG PY10X_CORE_VERSION
COPY constraints.txt /tmp/constraints.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    test -n "$PY10X_CORE_VERSION" \
    && uv pip install --system -c /tmp/constraints.txt "py10x-core==${PY10X_CORE_VERSION}" \
    && rm /tmp/constraints.txt

CMD ["python", "-c", "import core_10x; print('py10x-core', core_10x.__version__, 'ready')"]
