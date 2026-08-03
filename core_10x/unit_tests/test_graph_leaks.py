"""Reference-cycle / leak scenarios for Traitable, BTP-owned caches, and UI callbacks.

TODO(gc): Make kernel C++ types that hold Python objects (BTP / XCache / ObjectCache /
UI nodes, etc.) participate in the cyclic GC (``tp_traverse`` / ``tp_clear``, or
equivalent). Hybrid cycles such as::

    partial → BTP → owned XCache → UI node → partial
    GraphDeps.gp → BTP → owned cache → node values → …

are invisible to ``gc`` today, so these tests must break cycles explicitly
(``del g`` / ``del gd`` / ``data.clear()`` / ``XCache.clear()``). Once C++ objects
are GC-aware, cyclic collection should tear them down automatically and those
manual cleanups can be removed (or reduced to weakref-only assertions).
"""
from __future__ import annotations

import gc
import os
import weakref
from functools import partial

import pytest
from py10x_kernel import XCache, BTraitableProcessor

from core_10x.exec_control import BTP, GRAPH_ON, GraphDeps, INTERACTIVE
from core_10x.traitable import RT, Traitable


def test_ref_leak():
    class X(Traitable):
        x: Traitable

    x = X()
    x.x = X()
    wr_x = weakref.ref(x.x)

    del x
    assert wr_x()

    XCache.clear()
    assert not wr_x()


def test_graph_ref_leak():
    class X(Traitable):
        x: Traitable

    with GRAPH_ON() as g:
        x = X()
        x.x = X()
        wr_x, wr_g = weakref.ref(x.x), weakref.ref(g)

    del x
    assert wr_x()
    assert wr_g()

    del g  # TODO(gc): drop once BTP/XCache join cyclic GC (see module docstring)
    assert not wr_g()
    assert not wr_x()

@pytest.mark.parametrize(argnames='ctx', argvalues=[GRAPH_ON, BTraitableProcessor.create_root],ids=['GRAPH_ON','BTP.create_root'])
def test_self_ref_leak(ctx):
    class X(Traitable):
        x: Traitable

    with ctx() as g:
        x = X()
        x.x = x
        wr = weakref.ref(x)

    del x
    assert wr()

    del g  # TODO(gc): drop once BTP/XCache join cyclic GC (see module docstring)
    assert not wr()


def test_graph_deps_ref_leak():
    """GraphDeps.gp keeps the GRAPH_ON BTP alive after ``del g``, so node-held values stay too."""
    class X(Traitable):
        x: Traitable
        v: int = RT()
        out: int = RT()

        def out_get(self):
            return self.v

    with GRAPH_ON() as g:
        x = X()
        x.x = X()
        x.v = 1
        _ = x.out
        gd = GraphDeps(g, x.T.out, X, 'v')
        wr_x, wr_g = weakref.ref(x.x), weakref.ref(g)

    del x
    assert wr_x()
    assert wr_g()

    del g
    assert wr_g()  # still held by GraphDeps.gp
    assert wr_x()  # owned cache still alive with node value

    # TODO(gc): with GC-aware BTP/cache, ``del gd`` should not be required for
    # wr_* to die once no external roots remain (cycle should be collectable).
    del gd
    assert not wr_g()
    assert not wr_x()


def test_ui_node_callback_ref_leak():
    """UI refresh callbacks must not pin INTERACTIVE BTP / Traitable without a release path.

    ``create_ui_node`` stores ``f_refresh`` on a UI node on the INTERACTIVE owned cache.
    Binding ``partial(cb, BTP.current(), x, …)`` keeps::

      partial → BTP → owned XCache → UI node → partial  (+ partial → x)

    which survives ``del x`` and ``XCache.clear()`` (s_default only).

    Prefer a mutable bag: ``data = [BTP.current(), x, trait]`` with ``partial(cb, data)``.
    That still captures bind-time BTP for call-time comparison, and ``data.clear()``
    drops the strong refs so the cycle can die (same idea as ``del gd`` for GraphDeps).

    TODO(gc): once BTP / XCache / UI nodes participate in cyclic GC, pure cycles
    involving Python callbacks should be collectable without ``data.clear()``;
    keep the bag only if we still want an explicit bind-time BTP capture API.
    """
    class X(Traitable):
        x: int = RT()

    def _cb(data):
        btp, obj, trait = data
        assert BTP.current() == btp

    with INTERACTIVE():
        x = X(x=1)
        wr = weakref.ref(x)
        data = [BTP.current(), x, x.T.x]
        x.bui_class().create_ui_node(x, x.T.x, partial(_cb, data))
        x.x = 2

    del x
    data.clear()  # TODO(gc): remove when hybrid cycles are GC-breakable
    assert not wr()

