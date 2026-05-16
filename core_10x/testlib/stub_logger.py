"""Test doubles for ``core_10x.logger`` — no subprocess, no TsStore."""

from __future__ import annotations

from contextlib import contextmanager

import core_10x.logger as log_module


class StubLogPS:
    """Minimal ``psutil.Process`` stand-in for ``Logger`` / ``LOG._log``."""

    def memory_percent(self) -> float:
        return 0.0

    def num_threads(self) -> int:
        return 1


class StubLogLogger:
    """Records every dict passed to ``log()``; ``shutdown()`` is a no-op except for flags."""

    def __init__(self, log_level: int):
        self.log_level = log_level
        self.received: list = []
        self.ps = StubLogPS()
        self.shut_down = False

    def log(self, data) -> None:
        self.received.append(data)

    def shutdown(self) -> None:
        self.shut_down = True


@contextmanager
def stub_log_module_logger(log_level: int):
    """Temporarily set ``core_10x.logger.LOGGER`` to a ``StubLogLogger``; restore on exit."""
    prev = log_module.LOGGER
    stub = StubLogLogger(log_level)
    log_module.LOGGER = stub
    try:
        yield stub
    finally:
        log_module.LOGGER = prev
