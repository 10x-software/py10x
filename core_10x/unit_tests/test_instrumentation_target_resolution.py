import importlib
import sys

import pytest


def test_subclass_imported_while_resolving_an_earlier_target(modules, registry):
    # -- resolving 'a.BaseA' imports d (a subclass of the not-yet-resolved BaseB); d is neither target's module
    names = modules(
        {
            'b': 'class BaseB:\n    def m(self):\n        return 1\n',
            'd': 'from {b} import BaseB\nclass ChildB(BaseB):\n    def m(self):\n        return 2\n',
            'a': 'import {d}\nclass BaseA:\n    def m(self):\n        return 3\n',
        }
    )
    registry.set_target_base_classes(f'{names["a"]}.BaseA', f'{names["b"]}.BaseB')

    assert sys.modules[names['d']].ChildB in registry.instrumented_classes


def test_subclass_imported_while_resolving_a_later_target(modules, registry):
    # -- resolving 'b.BaseB' imports c (a subclass of the already-resolved BaseA)
    names = modules(
        {
            'a': 'class BaseA:\n    def m(self):\n        return 1\n',
            'c': 'from {a} import BaseA\nclass ChildA(BaseA):\n    def m(self):\n        return 2\n',
            'b': 'import {c}\nclass BaseB:\n    def m(self):\n        return 3\n',
        }
    )
    registry.set_target_base_classes(f'{names["a"]}.BaseA', f'{names["b"]}.BaseB')

    assert sys.modules[names['c']].ChildA in registry.instrumented_classes


def test_targets_own_modules_still_rewalked(modules, registry):
    names = modules({'a': 'class BaseA:\n    def m(self):\n        return 1\n\nclass ChildA(BaseA):\n    def m(self):\n        return 2\n'})
    registry.set_target_base_classes(f'{names["a"]}.BaseA')

    module = sys.modules[names['a']]
    assert {module.BaseA, module.ChildA} <= registry.instrumented_classes


@pytest.mark.parametrize('by_name', [False, True])
def test_target_module_imported_before_the_call(modules, registry, by_name):
    # -- the target's module is already in sys.modules, so nothing is imported while resolving it
    names = modules({'a': 'class BaseA:\n    def m(self):\n        return 1\n\nclass ChildA(BaseA):\n    def m(self):\n        return 2\n'})
    module = importlib.import_module(names['a'])
    registry.set_target_base_classes(f'{names["a"]}.BaseA' if by_name else module.BaseA)

    assert {module.BaseA, module.ChildA} <= registry.instrumented_classes
