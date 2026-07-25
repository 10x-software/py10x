"""Embedded-traitable serialization recurses without bound on a reference cycle.

An ``embeddable`` traitable held by a trait is serialized *inline* (full payload),
so a reference cycle among embeddable instances makes ``serialize`` recurse without
a base case: serialize_object -> serialize_traits -> BTrait::wrapper_f_serialize ->
Nucleus.serialize_any(EMBEDDED) -> serialize_object -> ...

On CPython the recursion limit trips first (RecursionError); on an ASan build with
inflated stack frames the native stack overflows first (STATUS_STACK_OVERFLOW /
0xC00000FD) - the intermittent Windows CI crash in test_traitable_history.

These tests assert the *desired* behavior - that ``serialize`` terminates on a cycle
instead of recursing unbounded - and are marked xfail until the kernel detects the
cycle. The recursion limit is capped low so the current failure is a deterministic
RecursionError that cannot hard-crash the test process on any platform; drop the cap
and the xfail marker once the cycle is handled.
"""

from __future__ import annotations

import sys

import pytest

from core_10x.exec_control import CACHE_ONLY
from core_10x.trait_definition import T
from core_10x.traitable import AnonymousTraitable
from core_10x.trait_method_error import TraitMethodError


class CyclicEmbeddable(AnonymousTraitable):
    peer: AnonymousTraitable = T()  # embeddable value -> serialized inline


# Expected to fail until embedded serialization detects reference cycles instead of recursing.
xfail_unbounded_recursion = pytest.mark.xfail(
    reason='embedded serialization recurses unbounded on a reference cycle - to be fixed in kernel',
    raises=(RecursionError, TraitMethodError),
    strict=True,
)


@xfail_unbounded_recursion
def test_self_referential_embeddable_serialize_terminates():
    with CACHE_ONLY():
        node = CyclicEmbeddable()
        node.peer = node  # self-cycle

        old = sys.getrecursionlimit()
        sys.setrecursionlimit(80)  # trip Python's guard before any native stack overflow
        try:
            node.serialize(True)  # should terminate; currently recurses unbounded
        finally:
            sys.setrecursionlimit(old)


@xfail_unbounded_recursion
def test_mutual_cycle_embeddable_serialize_terminates():
    with CACHE_ONLY():
        a = CyclicEmbeddable()
        b = CyclicEmbeddable()
        a.peer = b
        b.peer = a  # A embeds B embeds A

        old = sys.getrecursionlimit()
        sys.setrecursionlimit(80)
        try:
            a.serialize(True)  # should terminate; currently recurses unbounded
        finally:
            sys.setrecursionlimit(old)
