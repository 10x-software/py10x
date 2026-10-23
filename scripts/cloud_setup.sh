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
# The C++ packages (kernel/infra under cxx10x/, fin-base-cxx under xx_fin/cxxfin) build from this
# repo, as in any py10x dev env, so the image needs a C++ compiler; cmake/ninja come from the
# `build` dependency group. The build takes a few minutes - mind the setup-script time limit.
#
# Network: set the environment to "Trusted" and make sure github.com and PyPI
# are reachable (add github.com to Allowed domains if the clone fails).
set -euo pipefail

# A C++ compiler, if the image lacks one (sudo only when not already root).
if ! command -v c++ >/dev/null 2>&1; then
  SUDO=$(command -v sudo || true)
  $SUDO apt-get update
  $SUDO apt-get install -y --no-install-recommends build-essential
fi

# The dev environment (see dev_10x/README.md): build mode dev, so C++ edits rebuild on the next import.
./xx-build init

# Pre-pull the MongoDB image so the per-session start (see scripts/cloud_mongo.sh) is fast.
docker pull mongo:8 || true
