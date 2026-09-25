import __future__
import ast
import importlib.machinery
import inspect
import sys
import textwrap
from typing import Callable

from core_10x.package_refactoring import PackageRefactoring
from core_10x.trait import TRAIT_METHOD
from core_10x.traitable import Traitable, Trait


class CallableRewriter(ast.NodeTransformer):
    """
    Base class for a theme's per-function AST rewriter. A theme subclasses this, overriding whatever visit_*()
    methods it needs (ordinary ast.NodeTransformer convention), and populates self.globals_to_bind (in its own
    __init__, after calling super().__init__()) with whatever names its rewritten code needs live-bound into the
    target function's __globals__ to actually run.

    One instance is constructed once per theme and reused across every function it instruments -- instrument()
    derives filename fresh from each function itself (inspect.getsourcefile), so there's no need to construct a
    new rewriter per function.

    instrument() owns the ENTIRE per-function pipeline -- source extraction, parsing, line-number correction,
    decorator stripping, visiting, recompiling, and re-executing against the function's own globals -- so a theme
    only ever supplies the AST transformation itself, never the surrounding machinery.
    """

    def __init__(self):
        self.filename: str = None
        self.globals_to_bind: dict[str, object] = {}

    def location_id(self, node: ast.stmt | ast.expr) -> str:
        return f'{self.filename}:{node.lineno}'

    def instrument(self, function: Callable) -> Callable:
        self.filename = inspect.getsourcefile(function) or '<unknown>'
        source_lines, start_lineno = inspect.getsourcelines(function)
        source = textwrap.dedent(''.join(source_lines))
        tree = ast.parse(source)
        ast.increment_lineno(tree, start_lineno - 1)
        func_def = tree.body[0]
        if func_def.name != function.__name__:
            #-- e.g. a @cache-wrapped function: __name__ was reassigned to the original name, but
            # the actual source (what getsourcelines() sees) is the wrapper's own closure -- its
            # real body (the thing we'd want to instrument) is invisible behind an opaque call.
            # Nothing usable to rewrite here -- leave it exactly as-is.
            return function
        func_def.decorator_list = []   #-- strip any decorator getsource happened to capture -- caller re-wraps
        self.visit(func_def)
        ast.fix_missing_locations(tree)

        alt_globals = function.__globals__
        alt_globals.update(self.globals_to_bind)
        name = function.__name__
        #-- alt_globals IS function.__globals__ -- the DEFINING module's own __dict__, for both a
        # module-level function and a class method alike. exec() below would otherwise rebind (or,
        # for a method, spuriously introduce) `name` there as a side effect -- silently activating
        # a free function early, or leaking a stray module-level name for a method. Capture
        # whatever was at `name` first and put it straight back -- building must never leave a
        # trace; only apply()/restore() may actually activate anything.
        had_prior, prior_value = (name in alt_globals), alt_globals.get(name)
        #-- flags: re-parsing/recompiling just this function's own source loses the defining
        # module's own `from __future__ import annotations` effect -- without this, an annotation
        # referencing a TYPE_CHECKING-only import (never a real runtime name) would be eagerly
        # evaluated here and raise NameError, instead of staying the lazy string PEP 563 promises.
        code = compile(tree, self.filename, 'exec', flags = __future__.annotations.compiler_flag)
        exec(code, alt_globals)  # noqa: S102 -- deliberate: building an instrumented copy
        alt = alt_globals[name]
        if had_prior:
            alt_globals[name] = prior_value
        else:
            del alt_globals[name]
        return alt


class InstrumentationRegistry:
    """
    One instance = one instrumentation "theme" (e.g. aadc_exec's), with its own independent known-module/target-
    class/instrumented-callable state. The rewriter (a CallableRewriter instance, already fully configured for
    this theme) is the only theme-specific piece -- everything else here is generic bookkeeping.
    """

    def __init__(self, rewriter: CallableRewriter):
        self.rewriter = rewriter

        self.known_module_names: set[str]   = set()
        self.target_base_classes: set[type] = set()   #-- empty: auto-discovery instruments NO class until
        # the caller opts a base class in via set_target_base_classes() -- known_module_names coverage is
        # unaffected either way.
        self.exclude_classes: set[type]     = set()   #-- target_base_classes entries not instrumented themselves

        self.instrumented_callables: dict[tuple[object, str], tuple[Callable, Callable]] = {}  #-- (owner, attr_name) -> (original, instrumented)
        self.instrumented_getters: dict[Callable, Callable] = {}    #-- orig_getter -> instrumented_getter
        self.instrumented_classes: set[type] = set()                #-- guards instrument_class()'s recursion against cycles
        self.searched_classes: set[type] = set()                    #-- separate cycle guard for _search_for_target_classes()'s

        self._finder: InstrumentationFinder = None   #-- tracks the exact sys.meta_path entry, if installed

    def enable_auto_instrumentation(self):
        if self._finder is None:
            self._finder = InstrumentationFinder(self)
            sys.meta_path.insert(0, self._finder)

    def disable_auto_instrumentation(self):
        if self._finder is not None:
            sys.meta_path.remove(self._finder)
            self._finder = None

    def apply(self):
        Trait.set_use_instrumented_getters(True)
        for (owner, attr_name), (original, instrumented) in self.instrumented_callables.items():
            setattr(owner, attr_name, instrumented)

    def restore(self):
        Trait.set_use_instrumented_getters(False)
        for (owner, attr_name), (original, instrumented) in self.instrumented_callables.items():
            setattr(owner, attr_name, original)

    def register_modules(self, *module_names: str):
        self.known_module_names.update(module_names)

    def set_target_base_classes(self, *target_base_classes: type | str):
        """
        Replaces the current target base classes. Each entry may be an actual class object (used
        as-is) or a dotted class name (str), resolved via PackageRefactoring.find_class() -- lets a
        caller name a class without having to import it themselves first.
        """
        if target_base_classes:
            base_classes = self.target_base_classes
            base_classes.clear()
            modules_touched = set()
            for base_class in target_base_classes:
                if isinstance(base_class, str):
                    base_class = PackageRefactoring.find_class(base_class)
                base_classes.add(base_class)
                modules_touched.add(sys.modules[base_class.__module__])

            #-- resolving a name (or just referencing an already-imported class) may have imported
            # its module before base_classes above was complete -- re-walk it now, with the target
            # set finally settled, so the named class AND any sibling subclasses in the same module
            # get a fair (re-)evaluation. Safe to call even for a module already fully processed --
            # instrument_class()/instrument_if_target_class() are idempotent per class.
            for module in modules_touched:
                self.instrument_module(module)

    def set_exclude_classes(self, *exclude_classes: type | str):
        """
        Marks target_base_classes entries that should NOT be instrumented themselves -- their
        subclasses still match normally. Same type | str acceptance as set_target_base_classes.
        """
        if exclude_classes:
            classes = self.exclude_classes
            classes.clear()
            for cls in exclude_classes:
                if isinstance(cls, str):
                    cls = PackageRefactoring.find_class(cls)
                classes.add(cls)

    def instrument_module(self, module):
        if module.__name__ in self.known_module_names:
            self.instrument_known_module(module)
        else:
            #-- list(...): a snapshot, not a live view -- instrumenting one of this module's own
            # classes below can mutate this SAME module's __dict__ (CallableRewriter.instrument()
            # binds new globals into a method's defining module), which would otherwise raise
            # "dictionary changed size during iteration" reentrantly, one frame down.
            for name, member in list(vars(module).items()):
                if isinstance(member, type) and member.__module__ == module.__name__:
                    self.instrument_if_target_class(member)

    def instrument_known_module(self, module):
        for name, member in list(vars(module).items()):   #-- snapshot -- see instrument_module()
            if inspect.isfunction(member):
                if member.__module__ == module.__name__:
                    self.instrument_free_function(module, member)
            elif isinstance(member, type):
                if member.__module__ == module.__name__:
                    self.instrument_class(member)

    def instrument_if_target_class(self, cls):
        #-- match check comes BEFORE the cycle guard below, deliberately: set_target_base_classes()
        # may re-walk a module whose classes were already seen once under a since-replaced target
        # set (see its own comment) -- a class must always get a fresh match re-evaluation, even if
        # its NESTED-class recursion (searched_classes, below) already ran once.
        if cls not in self.exclude_classes and issubclass(cls, tuple(self.target_base_classes)):
            self.instrument_class(cls)
            return

        if cls in self.searched_classes:
            return

        self.searched_classes.add(cls)

        for name, member in list(vars(cls).items()):   #-- snapshot -- see instrument_module()
            if isinstance(member, type):
                self.instrument_if_target_class(member)   #-- not a match itself - keep looking for nested classes

    def instrument_class(self, cls):
        if cls in self.instrumented_classes:
            return
        self.instrumented_classes.add(cls)

        getter_suffix = f'_{TRAIT_METHOD.GET.name.lower()}'
        getter_suffix_len = len(getter_suffix)
        is_traitable = issubclass(cls, Traitable)
        trait_dir = cls.s_dir if is_traitable else None
        for name, member in list(vars(cls).items()):   #-- snapshot -- see instrument_module()
            if isinstance(member, classmethod) or isinstance(member, staticmethod) or inspect.isfunction(member):
                if is_traitable and name.endswith(getter_suffix):
                    trait = trait_dir.get(name[:-getter_suffix_len])
                    if trait:
                        self.instrument_getter(trait)
                    else:
                        self.instrument_method(cls, member)

                else:
                    self.instrument_method(cls, member)

            elif isinstance(member, type):      #-- deal with nested classes
                self.instrument_class(member)

    def instrument_method(self, target_class, method):
        func = method.__func__ if isinstance(method, (classmethod, staticmethod)) else method
        key = (target_class, func.__name__)
        if key in self.instrumented_callables:
            return

        if isinstance(method, classmethod):
            alt = classmethod(self.instrument_callable(func))
        elif isinstance(method, staticmethod):
            alt = staticmethod(self.instrument_callable(func))
        else:
            alt = self.instrument_callable(func)

        self.instrumented_callables[key] = (method, alt)

    def instrument_getter(self, trait: Trait):
        if not trait.has_custom_getter():
            return

        instrumented_getters = self.instrumented_getters
        original_f_get = trait.f_get
        instrumented_f_get = instrumented_getters.get(original_f_get)
        if not instrumented_f_get:
            instrumented_f_get = self.instrument_callable(original_f_get)
            instrumented_getters[original_f_get] = instrumented_f_get

        trait.set_f_get_instrumented(instrumented_f_get)

    def instrument_free_function(self, module, function):
        key = (module, function.__name__)
        if key not in self.instrumented_callables:
            instrumented_function = self.instrument_callable(function)
            self.instrumented_callables[key] = (function, instrumented_function)

    def instrument_callable(self, function) -> Callable:
        return self.rewriter.instrument(function)


class InstrumentationLoader(importlib.machinery.SourceFileLoader):
    def __init__(self, fullname, path, registry: InstrumentationRegistry):
        super().__init__(fullname, path)
        self.registry = registry

    def exec_module(self, module):
        super().exec_module(module)       #-- normal execution first, side effects run exactly once
        self.registry.instrument_module(module)   #-- then classify + instrument, post-execution


class InstrumentationFinder:
    def __init__(self, registry: InstrumentationRegistry):
        self.registry = registry

    def find_spec(self, fullname, path, target=None):
        spec = importlib.machinery.PathFinder.find_spec(fullname, path, target)
        if spec is None or spec.origin is None or not spec.origin.endswith('.py'):
            return None   #-- not a plain Python source module
        spec.loader = InstrumentationLoader(fullname, spec.origin, self.registry)
        return spec

