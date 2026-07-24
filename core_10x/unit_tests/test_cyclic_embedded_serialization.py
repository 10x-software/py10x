"""Reproduces the unbounded-recursion crash in embedded-traitable serialization.

An ``embeddable`` traitable held by a trait is serialized *inline* (full payload),
so a reference cycle among embeddable instances makes ``serialize`` recurse without
a base case: serialize_object -> serialize_traits -> BTrait::wrapper_f_serialize ->
Nucleus.serialize_any(EMBEDDED) -> serialize_object -> ...

On CPython the recursion limit trips first (RecursionError); on an ASan build with
inflated stack frames the native stack overflows first (STATUS_STACK_OVERFLOW /
0xC00000FD) - the intermittent Windows CI crash in test_traitable_history. The
recursion limit is capped low here so the failure is deterministic and cannot
hard-crash the test process on any platform.
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


def test_self_referential_embeddable_serialize_recurses_unbounded():
    with CACHE_ONLY():
        node = CyclicEmbeddable()
        node.peer = node  # self-cycle

        old = sys.getrecursionlimit()
        sys.setrecursionlimit(80)  # trip well before any native stack overflow
        try:
            with pytest.raises((RecursionError, TraitMethodError)):
                node.serialize(True)
        finally:
            sys.setrecursionlimit(old)


def test_mutual_cycle_embeddable_serialize_recurses_unbounded():
    with CACHE_ONLY():
        a = CyclicEmbeddable()
        b = CyclicEmbeddable()
        a.peer = b
        b.peer = a  # A embeds B embeds A

        old = sys.getrecursionlimit()
        sys.setrecursionlimit(80)
        try:
            with pytest.raises((RecursionError, TraitMethodError)):
                a.serialize(True)
        finally:
            sys.setrecursionlimit(old)
