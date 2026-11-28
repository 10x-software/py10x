from __future__ import annotations

import pytest
from core_10x.exec_control import CACHE_ONLY, DEBUG_ON, GRAPH_OFF, GRAPH_ON
from core_10x.scenario import Scenario
from core_10x.trait_definition import RT, T
from core_10x.trait_filter import EQ, f
from core_10x.traitable import Traitable
from core_10x.ui_hint import Ui

MAY_NOT_BE_SET = 'a READ_ONLY trait may not be set'


class Computed(Traitable):    #-- runtime only: no store is needed
    x: int  = RT(T.ID)
    a: int  = RT()
    v: int  = RT(T.READ_ONLY)
    d: int  = RT(7, T.READ_ONLY)

    def v_get(self) -> int:
        return self.a * 10


class Stored(Traitable):
    x: int  = T(T.ID)
    a: int  = T()
    v: int  = T(T.READ_ONLY)

    def v_get(self) -> int:
        return self.a * 10


def test_read_only_value_comes_from_the_getter_or_the_default():
    with GRAPH_ON():
        x   = Computed(x = 1)
        x.a = 2
        assert (x.v, x.d) == (20, 7)

        x.a = 3
        assert x.v == 30


def test_read_only_set_returns_a_failed_rc():
    with GRAPH_ON():
        x   = Computed(x = 1)
        x.a = 2

        for rc in (x.set_value('v', 5), x.set_values(v = 5), x.set_value('d', 8)):
            assert not rc
            assert MAY_NOT_BE_SET in rc.error()

        with pytest.raises(RuntimeError, match = MAY_NOT_BE_SET):
            x.v = 5

        assert (x.v, x.d) == (20, 7)


@pytest.mark.parametrize(
    'build',
    [
        lambda: Computed(x = 2, v = 5, _replace = True),
        lambda: Computed(x = 2, v = 5, _update = True),
        lambda: Computed.new_or_replace(x = 2, v = 5),
        lambda: Computed.new_or_update(x = 2, v = 5),
    ],
    ids = ['_replace', '_update', 'new_or_replace', 'new_or_update'],
)
def test_read_only_given_to_a_constructor_throws(build):
    with CACHE_ONLY(), pytest.raises(ValueError, match = MAY_NOT_BE_SET):
        build()


def test_read_only_may_be_set_as_a_what_if_below_the_objects_scope():
    """A set writes into the current scope: below the object's own it shadows the real value and goes with the scope."""
    with GRAPH_ON():
        x   = Computed(x = 1)
        x.a = 2

        with GRAPH_ON():
            x.v = 99
            assert x.v == 99

            x.a = 7                 #-- a value that was set does not follow the getter
            assert x.v == 99
            x.invalidate_value('v')
            assert x.v == 70

        assert (x.a, x.v) == (2, 20)

        with GRAPH_OFF():
            x.set_value('v', 77).throw()
            assert x.v == 77

        with Scenario():
            x.v = 55
            assert x.v == 55

        with Scenario('what if'):
            x.v = 66

        assert x.v == 20
        with Scenario('what if'):   #-- a named Scenario keeps its what-if values
            assert x.v == 66

        with pytest.raises(RuntimeError, match = MAY_NOT_BE_SET):
            x.v = 5


def test_read_only_is_refused_in_the_scope_its_object_lives_in():
    top     = Computed(x = 3)       #-- lives off graph, in the default cache
    top.a   = 2
    assert not top.set_value('v', 5)

    with GRAPH_ON():
        top.v = 99                  #-- a scope below it
        assert top.v == 99

        inner   = Computed(x = 4)   #-- lives in this scope
        inner.a = 1
        assert not inner.set_value('v', 5)
        with DEBUG_ON():            #-- another mode, the same scope
            assert not inner.set_value('v', 5)

    assert top.v == 20


def test_read_only_what_if_value_is_saved_as_the_scope_sees_it(ts_instance):
    """Nothing is added to save(): whoever saves from a what-if scope has made that choice."""
    with ts_instance, GRAPH_ON():
        s = Stored(x = 2, a = 2, _replace = True)
        s.save().throw()

        with GRAPH_ON():
            s.v = 99
            s.save().throw()
            assert Stored.load_data(s.id())['v'] == 99

        assert s.v == 20


def test_read_only_is_not_loaded():
    """The stored copy is for the store's searches only: a loaded value would no longer follow the getter."""

    class X(Traitable):
        x: int  = T(T.ID)
        a: int  = T()
        v: int  = T(T.READ_ONLY)

        def v_get(self) -> int:
            return self.a * 10

        @staticmethod
        def load_data(id):
            return {'_id': id.value, 'x': int(id.value), 'a': 2, 'v': 999, '_rev': 1}

        @classmethod
        def exists_in_store(cls, id):
            return True

    with CACHE_ONLY():
        x = X.deserialize_object(X.s_bclass, None, {'_id': '1', '_rev': 1, 'x': 1, 'a': 1, 'v': 999})
        assert x.v == 10

        x.a = 3
        assert x.v == 30

    lazy = X(x = 2)     #-- lazy load
    assert (lazy.a, lazy.v) == (2, 20)


def test_read_only_is_written_and_the_store_finds_by_it(ts_instance):
    with ts_instance:
        s = Stored(x = 1, a = 2, _replace = True)
        s.save().throw()
        assert Stored.load_data(s.id())['v'] == 20
        assert [found.x for found in Stored.load_many(f(v = EQ(20)))] == [1]

        s.a = 4
        s.save().throw()
        assert Stored.load_data(s.id())['v'] == 40
        assert Stored.load_many(f(v = EQ(20))) == []


def test_read_only_trait_is_read_only_in_a_form():
    class X(Traitable):
        v: int      = RT(T.READ_ONLY)
        shown: str  = RT(Ui(flags = Ui.READ_ONLY))
        plain: str  = RT()

    assert X.trait('v').ui_hint.flags_on(Ui.READ_ONLY)
    assert not X.trait('plain').ui_hint.flags_on(Ui.READ_ONLY)

    #-- the UI's own flag: a form may not edit it, and code still sets it
    assert X.trait('shown').ui_hint.flags_on(Ui.READ_ONLY)
    assert not X.trait('shown').flags_on(T.READ_ONLY)
    x       = X()
    x.shown = 'abc'
    assert x.shown == 'abc'


def test_old_name_is_gone():
    """`T.READONLY` meant "not editable in a form"; with the name kept, such a use would silently get the stricter meaning."""
    assert not hasattr(T, 'READONLY')
