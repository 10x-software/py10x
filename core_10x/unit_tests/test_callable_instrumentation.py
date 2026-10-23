from __future__ import annotations

import ast
import builtins
import importlib
import importlib.util
import inspect
import sys
import threading
import uuid

import pytest
from core_10x.callable_instrumentation import CallableRewriter, InstrumentationRegistry


def _write_module(directory, name: str, source: str):
    path = directory / f'{name}.py'
    path.write_text(source)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _GuardRewriter(CallableRewriter):
    """Wraps each `if` test with its location id so the guard filename survives as a code constant."""

    def __init__(self, barrier: threading.Barrier | None = None):
        super().__init__()
        self._barrier = barrier

    def visit_If(self, node: ast.If) -> ast.If:  # noqa: N802 -- ast.NodeTransformer callback name
        self.generic_visit(node)
        # Both threads have already passed instrument()'s filename write before either reads it.
        if self._barrier is not None:
            self._barrier.wait()
        node.test = ast.Call(
            func=ast.Name(id='__guard_id__', ctx=ast.Load()),
            args=[ast.Constant(value=self.location_id(node)), node.test],
            keywords=[],
        )
        return node


def _guard_id(function) -> str:
    ids = [const for const in function.__code__.co_consts if isinstance(const, str)]
    assert len(ids) == 1
    return ids[0]


@pytest.fixture
def empty_tuple_issubclass_raises(monkeypatch):
    # CPython returns False for issubclass(cls, ()). Treat that call as the TypeError the
    # finder must not hit, so an empty target set stays red if it is still passed through.
    real = builtins.issubclass

    def _issubclass(cls, classinfo):
        if classinfo == ():
            raise TypeError('issubclass() arg 2 must be a class, a tuple of classes, or a union')
        return real(cls, classinfo)

    monkeypatch.setattr(builtins, 'issubclass', _issubclass)


def test_empty_target_set_import_does_not_raise(tmp_path, monkeypatch, empty_tuple_issubclass_raises):
    module_name = f'ci_empty_targets_{uuid.uuid4().hex}'
    (tmp_path / f'{module_name}.py').write_text(
        'class Outer:\n'
        '    class Inner:\n'
        '        pass\n'
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    registry = InstrumentationRegistry(CallableRewriter())
    registry.enable_auto_instrumentation()
    try:
        module = importlib.import_module(module_name)
    finally:
        registry.disable_auto_instrumentation()
        sys.modules.pop(module_name, None)

    assert module.Outer in registry.searched_classes
    assert module.Outer.Inner in registry.searched_classes
    assert not registry.instrumented_classes


def test_string_target_instrumented_once_set_is_complete(tmp_path, monkeypatch, empty_tuple_issubclass_raises):
    module_name = f'ci_string_target_{uuid.uuid4().hex}'
    (tmp_path / f'{module_name}.py').write_text(
        'class Base:\n'
        '    def method(self):\n'
        '        return 1\n'
        '\n'
        'class Child(Base):\n'
        '    def method(self):\n'
        '        return 2\n'
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    registry = InstrumentationRegistry(CallableRewriter())
    registry.enable_auto_instrumentation()
    try:
        registry.set_target_base_classes(f'{module_name}.Base')
        module = sys.modules[module_name]
    finally:
        registry.disable_auto_instrumentation()
        sys.modules.pop(module_name, None)

    assert registry.target_base_classes == {module.Base}
    assert module.Base in registry.instrumented_classes
    assert module.Child in registry.instrumented_classes


def test_guard_id_uses_the_functions_own_filename(tmp_path):
    source = 'def check(flag):\n    if flag:\n        return 1\n    return 0\n'
    mod_a = _write_module(tmp_path, f'ci_file_a_{uuid.uuid4().hex}', source)
    mod_b = _write_module(tmp_path, f'ci_file_b_{uuid.uuid4().hex}', source)
    file_a = inspect.getsourcefile(mod_a.check)
    file_b = inspect.getsourcefile(mod_b.check)
    assert file_a != file_b

    rewriter = _GuardRewriter(barrier=threading.Barrier(2, timeout=5))
    results: dict[str, object] = {}
    errors: list[BaseException] = []

    def _run(key: str, function):
        try:
            results[key] = rewriter.instrument(function)
        except Exception as exc:  # noqa: BLE001 -- surface the barrier timeout instead of hanging
            errors.append(exc)

    threads = [
        threading.Thread(target=_run, args=('a', mod_a.check), daemon=True),
        threading.Thread(target=_run, args=('b', mod_b.check), daemon=True),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert not errors
    assert not any(thread.is_alive() for thread in threads)
    assert _guard_id(results['a']).startswith(f'{file_a}:')
    assert _guard_id(results['b']).startswith(f'{file_b}:')
