import faulthandler

# Fixtures / hooks (live_store, test_isolation, pytest_ignore_collect) come from the
# py10x-core pytest11 entry point (`dev_10x.pytest_plugin`). Keep this file for
# process-local setup only — pre-publish CI collects from site-packages and never
# loads the repo-root conftest.

faulthandler.enable()
