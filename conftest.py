import faulthandler

from core_10x.testlib.test_databases import live_store
from dev_10x.pytest_plugin import pytest_ignore_collect, test_isolation

faulthandler.enable()
