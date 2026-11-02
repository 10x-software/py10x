import sys
import uuid

import pytest
from core_10x.callable_instrumentation import CallableRewriter, InstrumentationRegistry


@pytest.fixture
def modules(tmp_path, monkeypatch):
    """Writes {short_name: source} as uniquely named modules; '{name}' in a source is replaced by that module's real name."""
    tag = uuid.uuid4().hex
    created = []

    def write(sources: dict[str, str]) -> dict[str, str]:
        names = {short: f'itr_{short}_{tag}' for short in sources}
        for short, source in sources.items():
            (tmp_path / f'{names[short]}.py').write_text(source.format(**names))
        created.extend(names.values())
        return names

    monkeypatch.syspath_prepend(str(tmp_path))
    yield write
    for name in created:
        sys.modules.pop(name, None)


@pytest.fixture
def registry():
    registry = InstrumentationRegistry(CallableRewriter())
    registry.enable_auto_instrumentation()
    yield registry
    registry.disable_auto_instrumentation()


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
