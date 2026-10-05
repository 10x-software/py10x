"""Tests for `dev_10x.xx_helpers.PyPIHelpers` (no network calls: `release_exists`, `urlopen` and the
`time` module are monkeypatched)."""

from __future__ import annotations

import io
import json
import time
from urllib import error, request

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


def test_release_json_cached_after_success_so_cdn_404_cannot_break_exact_pins(monkeypatch):
    """A fresh publish's JSON can 404 on a re-fetch right after `release_exists` saw it."""
    PyPIHelpers._release_json.cache_clear()
    body = {'urls': [{'filename': 'x.whl'}], 'info': {'requires_dist': ['py10x-kernel==1.2.3', 'numpy>=2']}}
    responses = [
        error.HTTPError('u', 404, 'Not Found', None, None),  # not published yet: not cached
        io.BytesIO(json.dumps(body).encode()),
        error.HTTPError('u', 404, 'Not Found', None, None),  # flaky CDN edge: must not be reached
    ]

    def fake_urlopen(url, timeout):
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        r.status = 200
        return r

    monkeypatch.setattr(request, 'urlopen', fake_urlopen)

    with pytest.raises(error.HTTPError):
        PyPIHelpers._release_json('py10x-core', '1.2.3', 10.0)
    assert PyPIHelpers._release_json('py10x-core', '1.2.3', 10.0) == body
    assert PyPIHelpers.exact_pins('py10x-core', '1.2.3', {'py10x-kernel'}) == {'py10x-kernel': '1.2.3'}
    PyPIHelpers._release_json.cache_clear()


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-v']))
