# First cut, scoped to the functional-account vault E2E test (see AGENTS.md task history).
# Reuses a CI-prepared checkout -- repo + a `.venv` already populated by
# `python -m dev_10x.uv_sync py10x-core-dev --all-extras` -- rather than a standalone
# wheel-publishing pipeline; that's a separate, bigger question (see dev_10x/README.md).
# Build from the repo root with that .venv already present:
#   docker build -f docker/Dockerfile -t py10x-functional-e2e .
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

# Generic placeholder account. docker/entrypoint.sh renames it to the pod's functional-account
# identity (FUNCTIONAL_ACCOUNT_ID) at container start, since VaultUser.myname() reads the real
# OS username with no override hook -- identity has to be real before any Python runs.
RUN useradd --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app
COPY . /app

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENV PATH="/app/.venv/bin:${PATH}"
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python", "-m", "pytest", "core_10x/unit_tests/test_functional_account_vault.py", "-v"]
