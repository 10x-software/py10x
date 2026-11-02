import ast
import builtins
import importlib
import sys
import threading
import time
import types
import uuid

import core_10x.callable_instrumentation as ci
from core_10x.callable_instrumentation import CallableRewriter

# -- Each test makes thread A wait up to WINDOW for thread B to reach the step it would race on. Unserialized, B
# gets there and the race happens deterministically; serialized, B is blocked, so A times out and finishes first.
WINDOW = 0.2
JOIN = 5


class _Worker(threading.Thread):
    def __init__(self, name: str, fn):
        super().__init__(name=name, daemon=True)
        self.fn = fn
        self.result = self.error = None

    def run(self):
        try:
            self.result = self.fn()
        except BaseException as e:  # noqa: BLE001 -- re-raised in the test thread by finish()
            self.error = e

    def finish(self):
        self.join(JOIN)
        assert not self.is_alive(), f'thread {self.name} did not finish (deadlock?)'
        if self.error is not None:
            raise self.error
        return self.result


def _in(name: str) -> bool:
    return threading.current_thread().name == name


class _GuardRewriter(CallableRewriter):
    """Tags each `if` with location_id(); pause() runs just before the id is read."""

    def __init__(self, pause):
        super().__init__()
        self.pause = pause

    def visit_If(self, node: ast.If) -> ast.If:  # noqa: N802 -- ast.NodeTransformer callback name
        self.generic_visit(node)
        self.pause()
        node.test = ast.Call(func=ast.Name(id='__guard__', ctx=ast.Load()), args=[ast.Constant(value=self.location_id(node)), node.test], keywords=[])
        return node


def test_shared_rewriter_keeps_each_functions_filename(modules):
    source = 'def check(flag):\n    if flag:\n        return 1\n    return 0\n'
    names = modules({'a': source, 'b': source})
    mod_a, mod_b = (importlib.import_module(names[key]) for key in ('a', 'b'))
    a_inside, b_inside = threading.Event(), threading.Event()

    def pause():
        if _in('A'):
            a_inside.set()
            b_inside.wait(WINDOW)  # -- unserialized, B overwrites the shared rewriter's filename meanwhile
        else:
            b_inside.set()

    rewriter = _GuardRewriter(pause)
    a = _Worker('A', lambda: rewriter.instrument(mod_a.check))
    b = _Worker('B', lambda: rewriter.instrument(mod_b.check))
    a.start()
    assert a_inside.wait(JOIN)
    b.start()

    for worker, module in ((a, mod_a), (b, mod_b)):
        guard_ids = [c for c in worker.finish().__code__.co_consts if isinstance(c, str) and ':' in c]
        assert guard_ids == [f'{module.__file__}:2']


def test_same_named_functions_built_into_one_module(modules, monkeypatch):
    # -- instrument() execs each def into the defining module's globals, then restores that name; two builds of
    # the same name (A.value, B.value) must not see each other's def. Separate rewriters: the lock is not per-instance.
    names = modules({'m': 'class A:\n    def value(self):\n        return 1\n\nclass B:\n    def value(self):\n        return 2\n'})
    module = importlib.import_module(names['m'])
    a_inside, b_execd, a_done = threading.Event(), threading.Event(), threading.Event()

    def exec_hook(code, globals_):
        builtins.exec(code, globals_)  # noqa: S102
        if _in('A'):
            a_inside.set()
            b_execd.wait(WINDOW)  # -- unserialized, B snapshots A's def as its "prior" and execs its own ...
        else:
            b_execd.set()
            a_done.wait(WINDOW)  # -- ... then A reads B's def back and deletes the name before B reads it

    monkeypatch.setattr(ci, 'exec', exec_hook, raising=False)

    def build_a():
        try:
            return CallableRewriter().instrument(module.A.value)
        finally:
            a_done.set()

    a = _Worker('A', build_a)
    b = _Worker('B', lambda: CallableRewriter().instrument(module.B.value))
    a.start()
    assert a_inside.wait(JOIN)
    b.start()

    assert a.finish().__code__.co_firstlineno == module.A.value.__code__.co_firstlineno
    assert b.finish().__code__.co_firstlineno == module.B.value.__code__.co_firstlineno
    assert 'value' not in vars(module)


def test_apply_while_an_import_adds_instrumented_callables(modules, registry):
    names = modules(
        {
            'a': (
                'class Meta(type):\n'
                '    hook = None\n'
                '    def __setattr__(cls, name, value):\n'
                '        if Meta.hook:\n'
                '            Meta.hook()\n'
                '        super().__setattr__(name, value)\n'
                '\n'
                'class Owner(metaclass=Meta):\n'
                '    def m(self):\n'
                '        return 1\n'
            ),
            'c': 'from {a} import Owner\n\nclass Child(Owner):\n    def m(self):\n        return 2\n',
        }
    )
    mod_a = importlib.import_module(names['a'])
    registry.set_target_base_classes(mod_a.Owner)
    a_inside, b_done = threading.Event(), threading.Event()

    def hook():
        if _in('A'):
            a_inside.set()
            b_done.wait(WINDOW)  # -- unserialized, B's import adds an entry while apply() iterates the table

    def import_c():
        try:
            return importlib.import_module(names['c'])
        finally:
            b_done.set()

    mod_a.Meta.hook = hook
    try:
        a = _Worker('A', registry.apply)
        b = _Worker('B', import_c)
        a.start()
        assert a_inside.wait(JOIN)
        b.start()
        a.finish()
        mod_c = b.finish()
    finally:
        mod_a.Meta.hook = None
        registry.restore()

    assert mod_c.Child in registry.instrumented_classes


def test_set_target_base_classes_while_its_module_is_being_imported(modules, registry):
    # -- B holds the target module's import lock (its body is still running); A resolves the same name. A must not
    # hold the instrumentation lock while it waits for that import, or B's loader blocks on it: deadlock.
    gate = types.ModuleType(f'itr_gate_{uuid.uuid4().hex}')
    gate.entered, gate.release = threading.Event(), threading.Event()
    sys.modules[gate.__name__] = gate
    try:
        names = modules(
            {'t': (f'import {gate.__name__} as gate\ngate.entered.set()\ngate.release.wait(5)\n\nclass Base:\n    def m(self):\n        return 1\n')}
        )
        b = _Worker('B', lambda: importlib.import_module(names['t']))
        b.start()
        assert gate.entered.wait(JOIN)
        a = _Worker('A', lambda: registry.set_target_base_classes(f'{names["t"]}.Base'))
        a.start()
        time.sleep(WINDOW)  # -- let A reach the import B is in the middle of
        gate.release.set()

        module = b.finish()
        a.finish()
    finally:
        gate.release.set()
        sys.modules.pop(gate.__name__, None)

    assert module.Base in registry.instrumented_classes
