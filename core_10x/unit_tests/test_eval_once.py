from __future__ import annotations

import pytest
from core_10x.exec_control import BTP, CACHE_ONLY, GRAPH_ON
from core_10x.trait_definition import RT, T
from core_10x.traitable import Traitable
from core_10x.traitable_id import ID
from core_10x.xnone import XNone


def test_eval_once_set_blocked():
    class X(Traitable):
        x: int = T(T.ID)
        v: int = T(T.EVAL_ONCE)

        def v_get(self):
            return self.x * 10

        @staticmethod
        def load_data(id):
            return {'_id': id.value, 'x': int(id.value), 'v': int(id.value) * 20, '_rev': 1}

        @classmethod
        def exists_in_store(cls, id):
            return True

    with CACHE_ONLY():
        x = X(x=1)
        assert x.v == 10
        with pytest.raises(TypeError, match='Trying to modify EVAL_ONCE trait'):
            x.v = 10

    # lazy load hydrates EVAL_ONCE from store when not yet evaluated
    x2 = X(x=2)
    assert x2.v == 40


def test_eval_once_uses_origin_cache_under_graph():
    """EVAL_ONCE stores on the object's origin cache (the GRAPH_ON child), not default_cache."""

    class X(Traitable):
        x: int = T(T.ID)
        v: int = T(T.EVAL_ONCE)
        calls = 0

        def v_get(self):
            type(self).calls += 1
            return 10

    with GRAPH_ON():
        x = X(x=1)
        assert x.v == 10
        assert X.calls == 1
        assert x.v == 10
        assert X.calls == 1

    with pytest.raises(RuntimeError, match='object not usable - origin cache is not reachable'):
        _ = x.v

    x = X(x=1)
    assert x.v == 10
    assert X.calls == 2
    assert x.v == 10
    assert X.calls == 2


def test_eval_once_under_create_root():
    """EVAL_ONCE nodes live on the object's origin cache."""

    class X(Traitable):
        x: int = T(T.ID)
        v: int = T(T.EVAL_ONCE)
        calls = 0

        def v_get(self):
            type(self).calls += 1
            return 10

    with CACHE_ONLY():
        default_cache = BTP.current().cache()
        outer = X(x=1)

        with BTP.create_root() as root:
            assert root.cache() is not default_cache
            assert BTP.current().cache() is root.cache()

            # outer's origin is default_cache; EVAL_ONCE stores there
            assert outer.v == 10
            assert X.calls == 1
            assert outer.v == 10
            assert X.calls == 1

            # object born under create_root evaluates on the orphan origin cache
            inner = X(x=2)
            assert inner.v == 10
            assert X.calls == 2

        # outer's EVAL_ONCE value survives create_root teardown (node on default_cache)
        assert outer.v == 10
        assert X.calls == 2
        with pytest.raises(TypeError, match='Trying to modify EVAL_ONCE trait'):
            outer.v = 99


def test_deserialize_skips_runtime_keeps_eval_once():
    """RUNTIME is never store-backed; EVAL_ONCE still deserializes when not yet valid."""

    class X(Traitable):
        a: int = T(T.ID)
        x: int = RT()
        y: int = T(T.EVAL_ONCE)

        def y_get(self):
            return 1

        @staticmethod
        def load_data(id):
            return {'_id': id.value, 'x': int(id.value) * 10, '_rev': 1, 'a': int(id.value)}

        @classmethod
        def exists_in_store(cls, id):
            return True

    with CACHE_ONLY():
        x = X.deserialize_object(X.s_bclass, None, {'_id': '1', '_rev': '1', 'x': 1, 'a': 1})
        assert x.x is XNone
        assert x.y == 1

        x.x = 2
        x1 = X.deserialize_object(X.s_bclass, None, {'_id': '1', '_rev': '1', 'x': 99, 'a': 1})
        assert x1.x == 2
        assert x1.y == 1

        x2 = X.deserialize_object(X.s_bclass, None, {'_id': '2', '_rev': '2', 'y': 2, 'a': 2})
        assert x2.y == 2
        assert x2.x is XNone

    lazy = X(_id=ID('3'))
    assert lazy.x is XNone
