import faulthandler

# Do NOT add pytest fixtures or hooks here. Register them on the py10x-core pytest11
# entry point (`dev_10x.pytest_plugin`) instead. Pre-publish CI collects from
# site-packages and never loads this repo-root conftest — fixtures only defined
# here will be missing there (e.g. live_store). Process-local setup only below.

faulthandler.enable()
