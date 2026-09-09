"""Sketch, not yet wired in anywhere. See xxfin/jit_aadc/aadc_kernel_doc.md for the full design
history and open questions this is drawn from.

EdgeDepsTracker registers value-dependent branches (`if` statements whose outcome could vary
across replay scenarios) as part of the dependency graph, so a consumer -- AADC recording is the
first one, via a subclass -- can detect when a branch taken during one evaluation differs from
what was recorded earlier, instead of silently trusting a stale recording.
"""

from __future__ import annotations

import ast
import importlib.machinery
import inspect
import sys
from typing import Callable

from core_10x.environment_variables import EnvVars
from core_10x.trait import Trait

ExecutionPath = frozenset[tuple[str, bool]]     #-- every (guard_id, outcome) pair hit in one evaluation


class EdgeDepsTracker:
    """
    One instance = one tracking session (e.g., the lifetime of one AadcKernel.build() call).
    Subclass to customize what happens with a recorded branch (see AadcEdgeDepsTracker) -- there
    is deliberately no separate provider protocol; EdgeDepsTracker itself is the base implementation,
    per EnvVars.edge_dep_tracker_class.
    """

    s_current: EdgeDepsTracker = None     #-- single global "active" pointer;
    # not thread-safe, not reentrant -- same accepted tradeoff as the C++-side dispatch flag this
    # pairs with for getters (see aadc_kernel_doc.md).

    s_instrumented_classes: dict[type, dict[str, Callable]] = {}     #-- target_cls -> {method_name: alt_callable};
    # centralized here rather than injected onto each target class, so EdgeDepsTracker owns all its own bookkeeping

    s_instrumented_modules: dict[str, dict[str, Callable]] = {}     #-- module __name__ -> {func_name: alt_callable};
    # same reasoning as s_instrumented_classes -- centralized here, not injected onto each target module

    def __init__(self):
        self.if_wrappers_log: list[tuple[str, object]] = []  #-- raw condition preserved (may be
        # a real ibool during AADC recording, not coerced to bool -- see if_wrapper below)
        self._patched: list[tuple[object, str, object]] = []  #-- (owner, name, original_value) --
        # exactly what THIS session patched, so __exit__ restores only that, not some global set

    def __enter__(self) -> EdgeDepsTracker:
        Trait.set_edge_deps_tracking(True)
        EdgeDepsTracker.s_current = self

        for target_cls, alt_methods in EdgeDepsTracker.s_instrumented_classes.items():
            for name, alt_func in alt_methods.items():
                self._patched.append((target_cls, name, vars(target_cls)[name]))
                setattr(target_cls, name, alt_func)

        for module_name, alt_funcs in EdgeDepsTracker.s_instrumented_modules.items():
            module = sys.modules.get(module_name)
            if module is None:
                continue  #-- not currently imported -- nothing to patch
            for name, alt_func in alt_funcs.items():
                self._patched.append((module, name, vars(module)[name]))
                setattr(module, name, alt_func)

        return self

    def __exit__(self, *args):
        for owner, name, original in self._patched:
            setattr(owner, name, original)
        self._patched.clear()

        Trait.set_edge_deps_tracking(False)
        EdgeDepsTracker.s_current = None

    @classmethod
    def if_wrapper(cls, guard_id: str, condition):
        """
        Call-site entry point: `if EdgeDepsTracker.if_wrapper(guard_id, cond): ...`.
        Transparent passthrough -- no-op whenever no tracker is active.
        """
        tracker = cls.s_current
        if tracker is not None:
            tracker.if_wrappers_log.append((guard_id, condition))  #-- raw, not bool(condition)

        return condition

    def execution_path(self) -> ExecutionPath:
        """
        bool() coercion happens here, not at record time -- the log itself must keep raw values
        (a real ibool during AADC recording) for a subclass to mark_as_output() later.
        """
        return frozenset((guard_id, bool(condition)) for guard_id, condition in self.if_wrappers_log)

    #------------------------------------------------------------------
    # Tier 1 -- class-scope instrumentation (any Traitable subclass's own methods)
    #------------------------------------------------------------------

    @classmethod
    def instrument_class(cls, target_traitable_class):
        """
        Called from Traitable.__init_subclass__, after cls.build_trait_dir() has populated
        cls.s_dir (needed below to recognize a genuine trait getter). Walks
        target_traitable_class's own __dict__ (not inherited members) once: a genuine trait
        getter (`{trait_name}_get`, matching a trait actually in s_dir) gets its alt version set
        directly via BTrait.set_f_get_edt(); everything else (ordinary method/classmethod/
        staticmethod) is registered in cls.s_instrumented_classes[target_traitable_class] as
        before. A separate pass afterward handles traits with no custom getter at all (or one
        inherited, not redefined here) -- they never appear in __dict__, so there's nothing to
        instrument; f_get_edt is just set to a copy of f_get.
        classmethod/staticmethod are descriptors wrapping .__func__ -- unwrap, instrument the
        inner function, re-wrap in the same descriptor type so a later caller invoking the alt
        version gets correct binding semantics (cls passed automatically for a classmethod, no
        implicit first arg for a staticmethod).
        """
        if_rewriter = cls.IfRewriter.instrument_function
        s_dir = target_traitable_class.s_dir
        handled_traits = set()

        alt_methods: dict[str, Callable] = {}
        for name, member in vars(target_traitable_class).items():
            trait_name = name[:-len('_get')] if name.endswith('_get') else None
            trait = s_dir.get(trait_name) if trait_name else None

            if trait is not None:
                trait.set_f_get_edt(if_rewriter(member))
                handled_traits.add(trait_name)
                continue

            if inspect.isfunction(member):
                alt_methods[name] = if_rewriter(member)
            elif isinstance(member, classmethod):
                alt_methods[name] = classmethod(if_rewriter(member.__func__))
            elif isinstance(member, staticmethod):
                alt_methods[name] = staticmethod(if_rewriter(member.__func__))

        #-- traits with no custom getter (or an inherited one, not redefined here) never
        # appeared in __dict__ above -- nothing to instrument, just reuse f_get as-is
        for trait_name, trait in s_dir.items():
            if trait_name not in handled_traits and not trait.has_custom_getter():
                trait.set_f_get_edt(trait.f_get)

        cls.s_instrumented_classes[target_traitable_class] = alt_methods

    #------------------------------------------------------------------
    # Tier 2 -- module-scope instrumentation (library modules, explicitly marked)
    #------------------------------------------------------------------

    MODULE_MARKER = '__track_edge_deps__'  #-- a marked module sets this to True at top level

    class IfRewriter(ast.NodeTransformer):
        """
        Wraps every If.test in a call to EdgeDepsTracker.if_wrapper(guard_id, test) --
        trivialist: no s_dir matching, no taint tracking, every If gets wrapped unfiltered
        (see aadc_kernel_doc.md for why this was chosen over a precise classifier).
        """

        def __init__(self, filename: str):
            self.filename = filename

        def visit_If(self, node: ast.If) -> ast.If:
            self.generic_visit(node)
            guard_id = f'{self.filename}:{node.lineno}'
            # goes through EnvVars.edge_dep_tracker_class, not a hardcoded class name: calling
            # a classmethod via a fixed name bypasses subclass polymorphism, silently skipping any
            # override a configured tracker subclass (e.g. AadcEdgeDepsTracker) makes to if_wrapper.
            node.test = ast.Call(
                func = ast.Attribute(
                    value = ast.Attribute(
                        value = ast.Name(id = 'EnvVars', ctx = ast.Load()),
                        attr = 'edge_dep_tracker_class', ctx = ast.Load(),
                    ),
                    attr = 'if_wrapper', ctx = ast.Load(),
                ),
                args = [ast.Constant(value = guard_id), node.test],
                keywords = [],
            )
            return node

        @classmethod
        def instrument_function(cls, func: Callable) -> Callable:
            filename = inspect.getsourcefile(func) or '<unknown>'
            source = inspect.getsource(func)
            tree = ast.parse(source)
            func_def = tree.body[0]
            func_def.decorator_list = []  #-- strip any decorators getsource happened to capture
            # (e.g. classmethod/staticmethod on the original) -- instrument_class re-wraps
            # explicitly based on the original descriptor type, so one surviving here would double-wrap
            cls(filename).visit(func_def)
            ast.fix_missing_locations(tree)

            alt_globals = dict(func.__globals__)
            alt_globals['EnvVars'] = EnvVars
            code = compile(tree, filename, 'exec')
            exec(code, alt_globals)  # noqa: S102 -- deliberate: building an instrumented copy
            return alt_globals[func.__name__]

    class IfFinder:
        #-- sys.meta_path entries are duck-typed (Python just calls find_spec); no ABC needed
        """
        Only installed at all when EnvVars.use_edge_deps_tracker is set -- zero cost for
        processes that never use this. Delegates to the standard PathFinder to locate the
        module first, then peeks at its source for the MODULE_MARKER sentinel; only marked
        modules get IfLoader substituted in, everything else is left completely alone (returning
        None here means "not my module," so the normal machinery loads it unmodified).
        """

        def find_spec(self, fullname, path, target = None):
            #-- goes through EnvVars.edge_dep_tracker_class throughout, not the hardcoded base --
            # a configured tracker subclass may override MODULE_MARKER or IfLoader itself.
            tracker_class = EnvVars.edge_dep_tracker_class
            spec = importlib.machinery.PathFinder.find_spec(fullname, path, target)
            if spec is None or spec.origin is None or not spec.origin.endswith('.py'):
                return None  #-- not a plain Python source module (namespace pkg, C ext, ...)

            with open(spec.origin, encoding = 'utf-8') as f:
                source = f.read()
            if tracker_class.MODULE_MARKER not in source:
                return None  #-- unmarked -- defer to the normal machinery, unmodified

            spec.loader = tracker_class.IfLoader(fullname, spec.origin)
            return spec

    class IfLoader(importlib.machinery.SourceFileLoader):
        """
        Executes a marked module's source normally first (so module-level side effects run
        exactly once, unmodified), then separately compiles+execs an instrumented copy of each
        top-level function against the same module globals, storing the results in
        EdgeDepsTracker.s_instrumented_modules[module.__name__].
        """

        def exec_module(self, module):
            super().exec_module(module)  #-- normal execution first -- side effects run exactly once

            #-- goes through EnvVars.edge_dep_tracker_class, not the hardcoded base class -- same
            # reasoning as visit_If: a literal EdgeDepsTracker reference would bypass any override
            # a configured tracker subclass makes to IfRewriter itself.
            tracker_class = EnvVars.edge_dep_tracker_class
            alt_funcs: dict[str, Callable] = {}
            if_rewriter = tracker_class.IfRewriter.instrument_function
            for name, member in vars(module).items():
                #-- only functions actually defined in this module, not ones merely imported
                # into it (those belong to, and get instrumented by, their own module if marked)
                if inspect.isfunction(member) and member.__module__ == module.__name__:
                    alt_funcs[name] = if_rewriter(member)
            tracker_class.s_instrumented_modules[module.__name__] = alt_funcs
