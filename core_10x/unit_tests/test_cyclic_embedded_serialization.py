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
