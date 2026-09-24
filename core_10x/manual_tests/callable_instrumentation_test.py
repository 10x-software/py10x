from core_10x.callable_instrumentation import CallableRewriter, InstrumentationRegistry
from core_10x.traitable import Traitable


class NoopRewriter(CallableRewriter):
    """Does nothing to the AST -- just enough of a CallableRewriter to build a registry with."""
    def visit_If(self, node):
        self.generic_visit(node)
        return node


class Unrelated:
    """Stand-in for "whatever the target scope happened to be before this call" -- deliberately
    unrelated to Traitable, to rule out set_target_base_classes() only working by accident of
    Traitable being both the {Traitable} default AND a universal ancestor of everything."""


class LocalTraitable(Traitable):
    """Used only to sanity-check instrument_if_target_class()'s cycle guard still terminates on
    Traitable's real s_history_class/s_traitable_class back-reference."""
    a: float = None


if __name__ == '__main__':
    TARGET_MODULE = 'core_10x.manual_tests.callable_instrumentation_target_module'

    #-- 1. set_target_base_classes() accepts a dotted class name (str), resolved lazily via
    #    PackageRefactoring.find_class() -- the caller never has to import the class themselves.
    #    Old scope deliberately unrelated, so a match here can't be Traitable-default luck.
    registry = InstrumentationRegistry(NoopRewriter())
    registry.enable_auto_instrumentation()
    registry.target_base_classes = {Unrelated}

    registry.set_target_base_classes(f'{TARGET_MODULE}.TargetBase')

    import core_10x.manual_tests.callable_instrumentation_target_module as target_module

    assert target_module.TargetBase in registry.instrumented_classes, \
        'named target base class itself should be instrumented'
    assert target_module.TargetChild in registry.instrumented_classes, \
        'sibling subclass in the SAME module, discovered as a side effect of resolving the ' \
        'name above, should ALSO be instrumented -- not silently missed'
    print('1. str-named target base class + same-module sibling: both instrumented, OK')

    #-- 2. set_target_base_classes() still accepts actual class objects directly too.
    registry_cls = InstrumentationRegistry(NoopRewriter())
    registry_cls.set_target_base_classes(target_module.TargetBase)
    assert registry_cls.target_base_classes == {target_module.TargetBase}
    print('2. class-object form: OK')

    #-- 3. set_exclude_classes() -- a target base class marked excluded is not instrumented
    #    itself, but its subclasses still match normally.
    registry_excl = InstrumentationRegistry(NoopRewriter())
    registry_excl.enable_auto_instrumentation()
    registry_excl.set_exclude_classes(f'{TARGET_MODULE}.TargetBase')
    registry_excl.set_target_base_classes(f'{TARGET_MODULE}.TargetBase')

    assert target_module.TargetBase not in registry_excl.instrumented_classes, \
        'excluded base class should NOT be instrumented'
    assert target_module.TargetChild in registry_excl.instrumented_classes, \
        'subclass should still be instrumented despite the base being excluded'
    print('3. exclude_classes: base excluded, subclass still covered, OK')

    #-- 4. instrument_if_target_class()'s cycle guard (searched_classes) still terminates on the
    #    real Traitable.s_history_class/s_traitable_class back-reference, even though the match
    #    check now runs BEFORE the guard (reordered to fix point 1 above).
    registry_cycle = InstrumentationRegistry(NoopRewriter())
    registry_cycle.target_base_classes = {Unrelated}   # won't match -- forces nested-class recursion
    registry_cycle.instrument_if_target_class(LocalTraitable)
    print('4. cycle guard still terminates on a real Traitable subclass, OK')

    print('\nAll callable_instrumentation manual checks passed.')
