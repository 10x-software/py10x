#!/bin/bash
# Cloud environment SETUP SCRIPT for Claude Code on the web.
#
# This file is NOT run automatically by the repo. Paste its body into the
# "Setup script" field of your cloud environment at claude.ai/code
# (cloud icon -> Add/Edit environment). It runs once per environment and is
# snapshot-cached (~7 days), so keep total runtime under ~5 minutes.
#
# Goal: a phone-driven session that reasons about docs, runs py10x code
# against MongoDB to verify assumptions, and edits documentation.
# No C++ build: the kernel/infra come from prebuilt PyPI wheels; cxx10x is
# cloned read-only purely as reference source.
#
# Network: set the environment to "Trusted" and make sure github.com and PyPI
# are reachable (add github.com to Allowed domains if the clone fails).
set -euo pipefail

# Kernel/infra (py10x-kernel, py10x-infra) from prebuilt PyPI wheels -- no C++ compilation.
# 'user' profile: core (this repo) editable-local, siblings from the package index.
uv run python dev_10x/uv_sync.py user --all-extras

# cxx10x source as read-only reference, placed where AGENTS.md expects it (../cxx10x).
# Public repo -> anonymous clone. '|| true' so a transient failure doesn't block the session.
git clone --depth 1 https://github.com/10x-software/cxx10x.git ../cxx10x || true

# Pre-pull the MongoDB image so the per-session start (see scripts/cloud_mongo.sh) is fast.
docker pull mongo:8 || true
