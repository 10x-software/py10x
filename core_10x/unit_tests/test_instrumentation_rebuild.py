import ast
import importlib
import sys

import pytest
from core_10x.callable_instrumentation import CallableRewriter


class _GuardRewriter(CallableRewriter):
    """Routes each `if` test through __guard__, which records the guard's line -- proves the rewritten code runs."""

    def __init__(self):
        super().__init__()
        self.hits = []
        self.globals_to_bind['__guard__'] = self.guard

    def guard(self, guard_id: str, condition):
        self.hits.append(int(guard_id.rsplit(':', 1)[1]))
        return condition

    def visit_If(self, node: ast.If) -> ast.If:  # noqa: N802 -- ast.NodeTransformer callback name
        self.generic_visit(node)
        node.test = ast.Call(
            func=ast.Name(id='__guard__', ctx=ast.Load()), args=[ast.Constant(value=self.location_id(node)), node.test], keywords=[]
        )
        return node


def _instrument(module, function):
    """Instruments `function` and checks the build left the defining module's globals alone."""
    rewriter = _GuardRewriter()
    before = {k: v for k, v in vars(module).items() if k not in rewriter.globals_to_bind}
    alt = rewriter.instrument(function)
    after = {k: v for k, v in vars(module).items() if k not in rewriter.globals_to_bind}
    assert after.keys() == before.keys() and all(after[k] is before[k] for k in before)
    assert alt is not function
    return alt, rewriter


SOURCE = '''
calls = []

def default_value():
    calls.append(1)
    return 2

def free(x=default_value(), *, y=[]):
    """free doc"""
    if x:
        return x, y
    return None

class Base:
    def value(self):
        return 1

    @classmethod
    def make(cls):
        return cls

class Derived(Base):
    SCALE = 3

    def __init__(self):
        self.__secret = 7

    def value(self):
        if True:
            return super().value() + 10

    @classmethod
    def make(cls):
        if True:
            return ('derived', super().make())

    def reveal(self, scale=SCALE) -> int:
        if scale:
            return self.__secret * scale

    def is_mine(self):
        if True:
            return isinstance(self, Derived)

class Outer:
    class Inner:
        def __init__(self):
            self.__x = 'inner'

        def get(self):
            if True:
                return self.__x

class run:
    def run(self):
        if True:
            return 'run'

def make_counter():
    count = 0

    def bump():
        nonlocal count
        if True:
            count += 1
        return count

    return bump

bump = make_counter()

def make_class():
    class C:
        def me(self):
            if True:
                return C
    return C

C = make_class()
'''


@pytest.fixture
def mod(modules):
    return importlib.import_module(modules({'m': SOURCE})['m'])


def test_zero_arg_super_in_method_and_classmethod(mod):
    alt, rewriter = _instrument(mod, mod.Derived.value)
    assert alt(mod.Derived()) == 11
    alt, _ = _instrument(mod, mod.Derived.make.__func__)
    assert alt(mod.Derived) == ('derived', mod.Derived)
    assert rewriter.hits


def test_private_names_mangled_with_the_innermost_class(mod):
    alt, _ = _instrument(mod, mod.Derived.reveal)
    assert alt(mod.Derived()) == 21
    alt, _ = _instrument(mod, mod.Outer.Inner.get)
    assert alt(mod.Outer.Inner()) == 'inner'


def test_class_attribute_default_and_own_class_name(mod):
    alt, _ = _instrument(mod, mod.Derived.reveal)  # -- default `scale=SCALE` only resolves in the class body
    assert alt.__defaults__ is mod.Derived.reveal.__defaults__
    alt, _ = _instrument(mod, mod.Derived.is_mine)  # -- `Derived` in the body stays a global name
    assert alt(mod.Derived()) is True


def test_defaults_are_shared_not_re_evaluated(mod):
    alt, rewriter = _instrument(mod, mod.free)
    assert mod.calls == [1]
    assert alt() == (2, mod.free.__kwdefaults__['y'])
    assert alt.__kwdefaults__['y'] is mod.free.__kwdefaults__['y']
    assert (alt.__name__, alt.__qualname__, alt.__doc__, alt.__module__) == ('free', 'free', 'free doc', mod.__name__)
    assert rewriter.hits == [mod.free.__code__.co_firstlineno + 2]


def test_closure_shares_cells_with_the_original(mod):
    alt, _ = _instrument(mod, mod.bump)
    assert (alt(), mod.bump(), alt()) == (1, 2, 3)


def test_class_that_is_itself_a_closure_variable(mod):
    alt, _ = _instrument(mod, mod.C.me)
    assert alt(mod.C()) is mod.C


def test_method_named_like_its_class(mod):
    alt, _ = _instrument(mod, mod.run.run)
    assert alt(mod.run()) == 'run'


@pytest.mark.skipif(sys.version_info < (3, 12), reason='PEP 695 syntax')
def test_generic_function(modules):
    module = importlib.import_module(modules({'g': 'def first[T](items: list[T]) -> T:\n    if items:\n        return items[0]\n'})['g'])
    alt, _ = _instrument(module, module.first)
    assert alt([5, 6]) == 5
    assert alt.__type_params__ == module.first.__type_params__
