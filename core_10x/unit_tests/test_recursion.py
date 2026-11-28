"""Runaway recursion through the kernel's callbacks ends in RecursionError, whatever the thread's stack size."""
import threading

import pytest

from core_10x.exec_control import GRAPH_OFF, GRAPH_ON
from core_10x.rc import RC
from core_10x.traitable import RT, T, Traitable


class Recursive(Traitable):
    name: str       = RT(T.ID)
    a: int          = RT()
    b: int          = RT()
    with_args: int  = RT()
    chained: int    = RT()
    s: int          = RT()
    u: int          = RT()
    choice: str     = RT()
    style: str      = RT()

    def a_get(self) -> int:
        return self.b + 1

    def b_get(self) -> int:
        return self.a + 1

    def with_args_get(self, n: int) -> int:
        return self.with_args(n + 1)

    def chained_get(self) -> int:
        return Recursive(name = self.name + 'x').chained

    def s_set(self, trait, value) -> RC:
        self.u = value
        return self.raw_set_trait_value(trait, value)

    def u_set(self, trait, value) -> RC:
        self.s = value
        return self.raw_set_trait_value(trait, value)

    def choice_choices(self, trait) -> tuple:
        return self.get_choices(trait)

    def style_style_sheet(self) -> dict:
        return self.get_style_sheet(Recursive.trait('style'))


RECURSIONS = {
    'getters':          lambda x: x.a,
    'getter_with_args': lambda x: x.with_args(0),
    'getter_chain':     lambda x: x.chained,        #-- no cycle: a new object at each level
    'setters':          lambda x: setattr(x, 's', 1),
    'choices':          lambda x: x.get_choices(Recursive.trait('choice')),
    'style_sheet':      lambda x: x.get_style_sheet(Recursive.trait('style')),
}


def run_in_thread(f, stack_size: int):
    """Returns f's exception, or its result. A stack overflow ends the process."""
    outcome = []

    def run():
        try:
            outcome.append(f())
        except BaseException as e:  # noqa: BLE001
            outcome.append(e)

    old_size = threading.stack_size(stack_size)
    try:
        thread = threading.Thread(target = run)
        thread.start()
    finally:
        threading.stack_size(old_size)
    thread.join()
    return outcome[0]


@pytest.mark.parametrize('graph', [GRAPH_ON, GRAPH_OFF])
@pytest.mark.parametrize('recursion', RECURSIONS)
def test_runaway_recursion_raises(recursion, graph):
    def f():
        with graph():
            with pytest.raises(Exception, match = 'RecursionError'):
                RECURSIONS[recursion](Recursive(name = 'x'))
            return Recursive(name = 'y').name       #-- the thread is usable afterwards

    assert run_in_thread(f, stack_size = 1024 * 1024) == 'y'


@pytest.mark.parametrize('stack_size', [256 * 1024, 512 * 1024])
def test_a_small_stack_still_runs_getters(stack_size):
    class Plain(Traitable):
        name: str = RT(T.ID)
        a: int    = RT()
        b: int    = RT()

        def a_get(self) -> int:
            return self.b + 1

        def b_get(self) -> int:
            return 1

    assert run_in_thread(lambda: Plain(name = 'x').a, stack_size) == 2
