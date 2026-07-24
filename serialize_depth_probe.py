"""Temporary pytest plugin: profile embedded-serialization recursion depth.

Wraps ``Traitable.serialize`` (the Python method the C++ backend re-enters per
embedded value) with a thread-local depth counter and reports, per test, the
deepest serialization reached. Distinguishes a *bounded-deep* structure (finite
max, e.g. ~50) from an *unbounded cycle* (depth climbs until RecursionError /
stack overflow), and names the exact triggering test.

Load with ``-p serialize_depth_probe`` (repo root is on sys.path under
``python -m pytest``). Diagnostic only; not part of the normal suite.
"""

from __future__ import annotations

import threading

import pytest

import core_10x.traitable as _tr

_tl = threading.local()
_state = {"max": 0, "type": None}
_orig = _tr.Traitable.serialize


def _wrapped(self, embed):
    d = getattr(_tl, "d", 0) + 1
    _tl.d = d
    try:
        if d > _state["max"]:
            _state["max"] = d
            _state["type"] = type(self).__name__
        return _orig(self, embed)
    finally:
        _tl.d = d - 1


_tr.Traitable.serialize = _wrapped

_rows: list[tuple[int, str, str]] = []


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    _state["max"] = 0
    _state["type"] = None
    yield
    if _state["max"] >= 15:
        _rows.append((_state["max"], _state["type"], item.nodeid))


def pytest_sessionfinish(session, exitstatus):
    print("\n=== deepest serialize recursion by test (depth >= 15) ===")
    for d, t, nid in sorted(_rows, reverse=True)[:30]:
        print(f"depth={d:6d}  value_type={t:26s}  {nid}")
    print("=== end serialize-depth report ===")
