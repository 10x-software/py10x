"""Unbounded recursion via save_references cascade on Root → (A↔B).

Non-embeddable refs with ``save_references`` ALL (1) or NEW_ONLY (2) cascade through
``serialize_nx`` → ``save(NONE)``. ``SerializationScope`` only memos the TID when
mode != 0, so cascaded children (mode 0) are never memoized while outer flags stay
active. Pattern::

    Root.save(NEW_ONLY|ALL)
      → serialize_object(mode)          # Root memoized
      → child A xref → A.save(NONE)     # A NOT memoized
      → peer B xref → B.save(NONE)      # B NOT memoized
      → peer A xref → A.save(NONE) → …  # infinite

Direct ``A↔B`` as the save root is finite (A is memoized). Default
``save_references=False`` (mode 0) does not cascade.

Caps the recursion limit so the failure is ``RecursionError`` /
``TraitMethodError`` instead of a native stack overflow under ASan.
"""

from __future__ import annotations

import sys
import time

import pytest
from typing_extensions import Self

from core_10x.trait_definition import T
from core_10x.trait_method_error import TraitMethodError
from core_10x.traitable import RC_TRUE, Traitable

from py10x_kernel import BSaveRefs

class Node(Traitable):
    k: int = T(T.ID)
    peer: Self = T()

class Root(Traitable):
    k: int = T(T.ID)
    child: Node = T()


@pytest.mark.parametrize('mode', [BSaveRefs.ALL,BSaveRefs.NEW_ONLY])
def test_root_over_mutual_cycle_save_references_recurses_unbounded(mode, ts_instance):
    with ts_instance:
        a = Node(k=int(time.time()*1000), _replace=True)
        b = Node(k=int(time.time()*1000), _replace=True)
        a.peer = b
        b.peer = a
        root = Root(k=int(time.time()*1000))
        root.child = a

        old = sys.getrecursionlimit()
        sys.setrecursionlimit(80)
        try:
            with pytest.raises((RecursionError, TraitMethodError)):
                root.serialize_object(save_references=int(mode))
        finally:
            sys.setrecursionlimit(old)

@pytest.mark.parametrize('mode', [BSaveRefs.ALL,BSaveRefs.NEW_ONLY])
def test_mutual_cycle_as_save_root_is_finite(mode, ts_instance):
    """A↔B saved as the root memos A; cascade of B→A is suppressed."""
    with ts_instance:
        a = Node(k=int(time.time()*1000), _replace=True)
        b = Node(k=int(time.time()*1000), _replace=True)
        a.peer = b
        b.peer = a
        a.serialize_object(save_references=int(mode))
