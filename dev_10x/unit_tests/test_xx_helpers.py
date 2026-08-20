"""Tests for `dev_10x.xx_helpers.PyPIHelpers.wait_for_release` (no network calls: `release_exists`
and the `time` module are monkeypatched)."""

from __future__ import annotations

import time

import pytest

from dev_10x.xx_helpers import PyPIHelpers


def _fake_clock(monkeypatch, sleeps: list[float]) -> None:
    """Fake `time.monotonic`/`time.sleep` sharing one clock: sleep(s) advances it by `s`."""
    now = [0.0]

    def fake_monotonic():
        return now[0]

    def fake_sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(time, 'monotonic', fake_monotonic)
    monkeypatch.setattr(time, 'sleep', fake_sleep)


def test_wait_for_release_returns_true_immediately_without_sleeping(monkeypatch):
    sleeps: list[float] = []
    _fake_clock(monkeypatch, sleeps)
    monkeypatch.setattr(PyPIHelpers, 'release_exists', classmethod(lambda cls, name, version: True))

    assert PyPIHelpers.wait_for_release('py10x-core', '1.2.3', deadline=1000.0, poll=90.0) is True
    assert sleeps == []


def test_wait_for_release_uses_quick_poll_then_backs_off(monkeypatch):
    sleeps: list[float] = []
    _fake_clock(monkeypatch, sleeps)
    calls = {'n': 0}

    def fake_exists(cls, name, version):
        calls['n'] += 1
        # first 2 checks fail (1 inside the quick-poll window, 1 after it backs off), then succeed.
        return calls['n'] > 2

    monkeypatch.setattr(PyPIHelpers, 'release_exists', classmethod(fake_exists))

    ok = PyPIHelpers.wait_for_release('py10x-infra', '1.2.3', deadline=1000.0, poll=90.0, quick_poll=10.0, quick_poll_window=5.0)

    assert ok is True
    # elapsed at 1st check: 0 (< 5 window -> quick 10s); elapsed at 2nd check: 10 (>= 5 -> full poll)
    assert sleeps == [10.0, 90.0]


def test_wait_for_release_times_out_returns_false_without_sleeping_past_deadline(monkeypatch):
    sleeps: list[float] = []
    _fake_clock(monkeypatch, sleeps)
    monkeypatch.setattr(PyPIHelpers, 'release_exists', classmethod(lambda cls, name, version: False))

    ok = PyPIHelpers.wait_for_release('py10x-infra', '1.2.3', deadline=0.0, poll=90.0, quick_poll=10.0)

    assert ok is False
    assert sleeps == []


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-v']))
