import importlib
import pkgutil
import sys

import pytest
import xxcommon

import xxfin

_SELECTORS = ('xxcommon.curve', 'xxfin.rate_curve', 'xxfin.day_count_convention', 'xxfin.ir_compounding', 'xxfin.zrc_bootstrap')
_IMPLEMENTATIONS = {
    f'{package}.{kind}_{name}'
    for package, name in (('xxcommon', 'curve'), ('xxfin', 'rate_curve'), ('xxfin', 'day_count_convention'), ('xxfin', 'ir_compounding'), ('xxfin', 'zrc_bootstrap'))
    for kind in ('py', 'cxx')
}
_SKIPPED_PACKAGES = {'unit_tests', 'manual_tests', 'attic', 'testlib'}


def _import_all(package) -> list:
    modules = []
    for info in pkgutil.iter_modules(package.__path__, f'{package.__name__}.'):
        if info.name.rsplit('.', 1)[-1] in _SKIPPED_PACKAGES:
            continue
        try:
            module = importlib.import_module(info.name)
        except ImportError:     # an optional dependency (blpapi, aadc, ...) is not installed
            continue
        modules.append(module)
        if info.ispkg:
            modules += _import_all(module)
    return modules


#-- imported at collection, before any use_cxx switch, so each module binds what it does in a real run
_MODULES = _import_all(xxcommon) + _import_all(xxfin)


def _stale_bindings() -> list:
    stale = []
    for selector in map(sys.modules.get, _SELECTORS):
        for name, current in vars(selector).items():
            if getattr(current, '__module__', None) not in _IMPLEMENTATIONS:
                continue
            for module in _MODULES:
                obj = module.__dict__.get(name)
                if obj is None or obj is current or module is selector:
                    continue
                obj_module = getattr(obj, '__module__', None)
                if obj_module in _IMPLEMENTATIONS and obj_module != module.__name__:
                    stale.append(f'{module.__name__}.{name} -> {obj_module}')
    return sorted(set(stale))


@pytest.mark.usefixtures('cxx_or_py_curve_consumers')
def test_no_module_keeps_the_other_implementation():
    stale = _stale_bindings()
    assert not stale, 'still bound to the other implementation:\n' + '\n'.join(stale)
