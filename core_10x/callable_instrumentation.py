import ast
import importlib.machinery
import inspect
import sys
import textwrap
from typing import Callable

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
        code = compile(tree, self.filename, 'exec')
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
        self.target_base_classes: set[type] = { Traitable }

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
        Trait.set_edge_deps_tracking(True)
        for (owner, attr_name), (original, instrumented) in self.instrumented_callables.items():
            setattr(owner, attr_name, instrumented)

    def restore(self):
        Trait.set_edge_deps_tracking(False)
        for (owner, attr_name), (original, instrumented) in self.instrumented_callables.items():
            setattr(owner, attr_name, original)

    def register_modules(self, *module_names: str):
        self.known_module_names.update(module_names)

    def set_target_base_classes(self, *target_base_classes):
        if target_base_classes:
            base_classes = self.target_base_classes
            base_classes.clear()
            for base_class in target_base_classes:
                assert issubclass(base_class, Traitable), f'{base_class} is not a subclass of Traitable'
                base_classes.add(base_class)

    def instrument_module(self, module):
        if module.__name__ in self.known_module_names:
            self.instrument_known_module(module)
        else:
            for name, member in vars(module).items():
                if isinstance(member, type) and member.__module__ == module.__name__:
                    self.instrument_if_target_class(member)

    def instrument_known_module(self, module):
        for name, member in vars(module).items():
            if inspect.isfunction(member):
                if member.__module__ == module.__name__:
                    self.instrument_free_function(module, member)
            elif isinstance(member, type):
                if member.__module__ == module.__name__:
                    self.instrument_class(member)

    def instrument_if_target_class(self, cls):
        if cls in self.searched_classes:
            return

        self.searched_classes.add(cls)

        if issubclass(cls, tuple(self.target_base_classes)):
            self.instrument_class(cls)
            return

        for name, member in vars(cls).items():
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
        for name, member in vars(cls).items():
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
        key = (target_class, method.__name__)
        if key in self.instrumented_callables:
            return

        if isinstance(method, classmethod):
            alt = classmethod(self.instrument_callable(method.__func__))
        elif isinstance(method, staticmethod):
            alt = staticmethod(self.instrument_callable(method.__func__))
        else:
            alt = self.instrument_callable(method)

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

        trait.set_f_get_edt(instrumented_f_get)

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

