"""Unit tests for core_10x/logger.py.

Logger itself (and LOG.begin/end) require a live subprocess, OsUser (C++ kernel),
and an optional TsStore — those are exercised by manual/integration tests.
This suite covers the pure-Python parts that have no external dependencies:
PerfTimer and the LOG level constants / guard assertion.
"""
import time

import pytest

import core_10x.logger as log_module
from core_10x.logger import LOG, PerfTimer


# ---------------------------------------------------------------------------
# PerfTimer
# ---------------------------------------------------------------------------

class TestPerfTimer:
    def test_elapsed_is_positive(self):
        with PerfTimer() as t:
            time.sleep(0.001)
        assert t.elapsed > 0

    def test_elapsed_in_nanoseconds(self):
        """sleep(0.01) = 10ms; elapsed must be at least 10_000_000 ns."""
        with PerfTimer() as t:
            time.sleep(0.01)
        assert t.elapsed >= 10_000_000

    def test_start_before_end(self):
        with PerfTimer() as t:
            pass
        assert t.start < t.end

    def test_elapsed_equals_end_minus_start(self):
        with PerfTimer() as t:
            pass
        assert t.elapsed == t.end - t.start

    def test_returns_self(self):
        timer = PerfTimer()
        with timer as ctx:
            assert ctx is timer


# ---------------------------------------------------------------------------
# LOG level constants
# ---------------------------------------------------------------------------

class TestLOGLevels:
    def test_brief_value(self):
        assert LOG.BRIEF.value == 0

    def test_medium_value(self):
        assert LOG.MEDIUM.value == 1

    def test_detailed_value(self):
        assert LOG.DETAILED.value == 2

    def test_verbose_value(self):
        assert LOG.VERBOSE.value == 3

    def test_levels_are_ordered(self):
        assert LOG.BRIEF.value < LOG.MEDIUM.value < LOG.DETAILED.value < LOG.VERBOSE.value

    def test_log_levels_are_callable(self):
        """Each level attribute must be callable (even without an active Logger)."""
        for attr in ('BRIEF', 'MEDIUM', 'DETAILED', 'VERBOSE'):
            assert callable(getattr(LOG, attr))


# ---------------------------------------------------------------------------
# LOG guard — raises when no Logger is active
# ---------------------------------------------------------------------------

class TestLOGGuard:
    def _with_no_logger(self, fn):
        """Temporarily clear LOGGER and call fn, then restore."""
        original = log_module.LOGGER
        log_module.LOGGER = None
        try:
            fn()
        finally:
            log_module.LOGGER = original

    def test_brief_raises_without_logger(self):
        with pytest.raises(AssertionError, match='LOG.begin'):
            self._with_no_logger(lambda: LOG.BRIEF('hello'))

    def test_medium_raises_without_logger(self):
        with pytest.raises(AssertionError, match='LOG.begin'):
            self._with_no_logger(lambda: LOG.MEDIUM('hello'))

    def test_detailed_raises_without_logger(self):
        with pytest.raises(AssertionError, match='LOG.begin'):
            self._with_no_logger(lambda: LOG.DETAILED('hello'))

    def test_verbose_raises_without_logger(self):
        with pytest.raises(AssertionError, match='LOG.begin'):
            self._with_no_logger(lambda: LOG.VERBOSE('hello'))

    def test_none_payload_skips_data_construction(self):
        """_log with payload=None sends None to the queue; no crash when LOGGER is set."""
        # We can't instantiate a real Logger without OsUser, but we can
        # verify that _log short-circuits correctly for None payload by
        # providing a minimal stub.
        class StubLogger:
            log_level = 0
            ps = None
            received = None
            def log(self, data): StubLogger.received = data

        original = log_module.LOGGER
        log_module.LOGGER = StubLogger()
        try:
            LOG._log(0, None)
            assert StubLogger.received is None
        finally:
            log_module.LOGGER = original
