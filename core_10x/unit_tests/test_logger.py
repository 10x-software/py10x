"""Unit tests for core_10x/logger.py.

Structure
---------
TestPerfTimer       - context-manager timing mechanics (no deps beyond stdlib)
TestLOGLevels       - level constants and callability
TestLOGGuard        - _log raises without an active Logger
TestLoggerEndToEnd  - subprocess lifecycle using Logger directly;
                      full message-processing requires a TsStore (infra_10x tests)
TestLOGStub         - functional tests of the LOG interface using a stub Logger
                      (``stub_log_logger`` fixture — avoids subprocess / TsStore)
"""

import multiprocessing as mp
import time

import pytest

import core_10x.logger as log_module
from core_10x.logger import LOG, Logger, PerfTimer
from core_10x.testlib.stub_logger import stub_log_module_logger


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
        with pytest.raises(RuntimeError, match=r'LOG.begin'):
            self._with_no_logger(lambda: LOG.BRIEF('hello'))

    def test_medium_raises_without_logger(self):
        with pytest.raises(RuntimeError, match=r'LOG.begin'):
            self._with_no_logger(lambda: LOG.MEDIUM('hello'))

    def test_detailed_raises_without_logger(self):
        with pytest.raises(RuntimeError, match=r'LOG.begin'):
            self._with_no_logger(lambda: LOG.DETAILED('hello'))

    def test_verbose_raises_without_logger(self):
        with pytest.raises(RuntimeError, match=r'LOG.begin'):
            self._with_no_logger(lambda: LOG.VERBOSE('hello'))

    def test_none_payload_skips_data_construction(self):
        """_log with payload=None sends None to the queue; no crash when LOGGER is set."""
        with stub_log_module_logger(LOG.BRIEF.value) as stub:
            LOG._log(0, None)
            assert stub.received == [None]


# ---------------------------------------------------------------------------
# End-to-end: Logger subprocess lifecycle
# ---------------------------------------------------------------------------


class TestLoggerEndToEnd:
    """
    Tests that exercise the real Logger subprocess (requires OsUser / py10x_kernel).

    Full message-processing (LogMessage.save) needs a live TsStore and is covered
    by infra_10x integration tests.  Here we verify:
      - the subprocess starts correctly
      - the IPC queue works
      - clean shutdown when the first queue item is the sentinel (None)
    """

    def test_subprocess_starts_and_stops_cleanly(self):
        """Logger starts a daemon subprocess; immediate shutdown exits with code 0."""
        logger = Logger('e2e_test_start_stop', LOG.BRIEF.value, do_print=False)
        assert logger.proc.is_alive()

        logger.shutdown()          # puts None → subprocess returns immediately
        assert logger.proc.exitcode == 0

    def test_queue_accepts_shutdown_signal(self):
        """The queue can carry the None sentinel without blocking."""
        logger = Logger('e2e_test_queue', LOG.BRIEF.value, do_print=False)
        logger.shutdown()
        # After join the queue should be drained
        assert logger.proc.exitcode == 0

    def test_multiple_loggers_can_run_concurrently(self):
        """Two independent Logger instances do not interfere with each other."""
        l1 = Logger('e2e_test_multi_1', LOG.BRIEF.value, do_print=False)
        l2 = Logger('e2e_test_multi_2', LOG.BRIEF.value, do_print=False)

        assert l1.proc.pid != l2.proc.pid

        l1.shutdown()
        l2.shutdown()

        assert l1.proc.exitcode == 0
        assert l2.proc.exitcode == 0


# ---------------------------------------------------------------------------
# Functional: LOG interface via stub_log_logger fixture
# ---------------------------------------------------------------------------


class TestLOGStub:
    """Exercise ``LOG.*`` against ``StubLogLogger`` (no subprocess)."""

    def test_brief_message_is_delivered(self, stub_log_logger):
        LOG.BRIEF('hello')
        assert len(stub_log_logger.received) == 1
        assert stub_log_logger.received[0]['payload'] == 'hello'
        assert stub_log_logger.received[0]['level'] == LOG.BRIEF.value

    @pytest.mark.parametrize('stub_log_logger', [LOG.VERBOSE.value], indirect=True)
    def test_all_levels_delivered_at_verbose(self, stub_log_logger):
        LOG.BRIEF('a')
        LOG.MEDIUM('b')
        LOG.DETAILED('c')
        LOG.VERBOSE('d')
        assert len(stub_log_logger.received) == 4

    def test_high_level_messages_filtered_at_brief(self, stub_log_logger):
        """Only BRIEF messages pass when log_level == BRIEF.value (0)."""
        LOG.BRIEF('kept')
        LOG.MEDIUM('dropped')
        LOG.DETAILED('dropped')
        LOG.VERBOSE('dropped')
        assert len(stub_log_logger.received) == 1
        assert stub_log_logger.received[0]['payload'] == 'kept'

    def test_message_contains_required_fields(self, stub_log_logger):
        LOG.BRIEF({'key': 'value'})
        msg = stub_log_logger.received[0]
        assert 'ns' in msg
        assert 'level' in msg
        assert 'mem_pc' in msg
        assert 'num_threads' in msg
        assert 'payload' in msg

    def test_ns_is_monotonically_increasing(self, stub_log_logger):
        for _ in range(10):
            LOG.BRIEF('tick')
        timestamps = [m['ns'] for m in stub_log_logger.received]
        assert timestamps == sorted(timestamps)

    @pytest.mark.parametrize('stub_log_logger', [LOG.VERBOSE.value], indirect=True)
    def test_payload_can_be_any_type(self, stub_log_logger):
        LOG.BRIEF(42)
        LOG.BRIEF({'nested': True})
        LOG.BRIEF([1, 2, 3])
        payloads = [m['payload'] for m in stub_log_logger.received]
        assert payloads == [42, {'nested': True}, [1, 2, 3]]

    def test_perftimer_elapsed_can_be_logged(self, stub_log_logger):
        """PerfTimer.elapsed can be passed directly as a log payload."""
        with PerfTimer() as t:
            _ = sum(range(100_000))
        LOG.BRIEF({'elapsed_ns': t.elapsed})
        msg = stub_log_logger.received[0]
        assert msg['payload']['elapsed_ns'] == t.elapsed
        assert t.elapsed > 0

    def test_end_calls_shutdown_and_resets_logger(self, stub_log_logger):
        """LOG.end() must call shutdown() on the active logger and set LOGGER to None."""
        LOG.end()
        assert stub_log_logger.shut_down is True
        assert log_module.LOGGER is None

    def test_end_is_idempotent_when_no_logger(self):
        """LOG.end() must not raise when LOGGER is already None."""
        assert log_module.LOGGER is None
        LOG.end()   # should be a no-op

    def test_logger_can_be_restarted_after_end(self, stub_log_logger):
        """After LOG.end() resets LOGGER, a new stub logger can be installed and used."""
        LOG.end()
        assert log_module.LOGGER is None

        with stub_log_module_logger(LOG.BRIEF.value) as stub2:
            LOG.BRIEF('after restart')
            assert len(stub2.received) == 1
            assert stub2.received[0]['payload'] == 'after restart'
