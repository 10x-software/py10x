"""
Sketch (2026-09-16): warning-driven, on-demand instrumentation for AadcExec.

Replaces bulk monkey-patching entirely -- both Tier-1 ("wrap every `if` in every Traitable
getter unconditionally at class-definition time") and AADCContext's process-wide
builtins/math.* patching -- with targeted instrumentation driven purely by aadc's own
kernel.passive_warnings() diagnostics, discovered on demand as each kernel is built.

Not wired into aadc_exec.py yet. See conversation history for the full design walk-through:
create_kernel() would (1) run a plain, wholly uninstrumented get_trait_value() pass just to
discover MktDeps, (2) build a throwaway "calibration" kernel (no signature/guard value from
this -- it's disposable, possibly already silently wrong on replay wherever a passive warning
fired), (3) walk kernel.passive_warnings(), instrument each relevant location via the
functions below, (4) rebuild for real against the same market data (deterministic, so this
reproduces the same branches/values) to get the kernel actually kept in AadcExec.kernels.
"""

from __future__ import annotations

import ast
import inspect
import linecache
import math
import os
import sys
import textwrap

import aadc

from core_10x.edge_deps_tracker import EdgeDepsTracker
from core_10x.traitable import Traitable


#------------------------------------------------------------------
# file:line -> qualname
#------------------------------------------------------------------

class DefLocator(ast.NodeVisitor):
    """
    Finds the dotted qualname of the innermost def (function, method, or nested closure)
    containing a given line -- e.g. for resolving aadc's kernel.passive_warnings() locations
    to the function that needs instrumenting. AST-based (source text only), not object-graph
    scanning: a closure only exists as a live object during its enclosing call, so scanning
    for a matching code object after the fact silently matches the wrong (outer) function
    instead -- confirmed empirically 2026-09-16.
    """

    def __init__(self, line: int):
        self.line = line
        self.stack: list[str] = []
        self.found: str = None

    def _visit_def(self, node):
        self.stack.append(node.name)
        if node.lineno <= self.line <= (node.end_lineno or node.lineno):
            self.found = '.'.join(self.stack)
        self.generic_visit(node)
        self.stack.pop()

    visit_FunctionDef = _visit_def
    visit_AsyncFunctionDef = _visit_def

    def visit_ClassDef(self, node):
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    @classmethod
    def find(cls, file: str, line: int) -> str:
        source = ''.join(linecache.getlines(file))
        if not source:
            return None
        locator = cls(line)
        locator.visit(ast.parse(source, filename = file))
        return locator.found


#------------------------------------------------------------------
# qualname -> live (owner, name, obj)
#------------------------------------------------------------------

def resolve_module(file: str):
    file = os.path.normcase(os.path.abspath(file))
    for mod in sys.modules.values():
        mod_file = getattr(mod, '__file__', None)
        if mod_file and os.path.normcase(os.path.abspath(mod_file)) == file:
            return mod
    return None


def resolve_qualname(module, qualname: str):
    """
    Walks qualname's dotted segments from `module` via getattr, stopping at the deepest
    segment that actually resolves. A segment that fails to resolve means everything past it
    is a closure -- only reachable while its enclosing call is running, never an attribute of
    anything -- so this naturally lands on the nearest addressable ancestor instead of
    failing outright. DefLocator only ever terminates a qualname on a genuine def, so a
    fully-successful walk always ends on a real function object.
    """
    owner, obj, name = module, module, None
    for segment in qualname.split('.'):
        candidate = getattr(obj, segment, None)
        if candidate is None:
            break
        owner, obj, name = obj, candidate, segment
    return (owner, name, obj)


def _resolve_target(file: str, line: int):
    """
    Common to both warning kinds: file:line -> (owner, name, original_obj), or None if it
    can't be structurally instrumented (out of scope, unresolvable, not a plain function --
    classmethod/staticmethod descriptors aren't handled here yet, unlike
    EdgeDepsTracker.instrument_class, which unwraps them explicitly).
    """
    qualname = DefLocator.find(file, line)
    if qualname is None:
        return None

    module = resolve_module(file)
    if module is None:
        return None

    owner, name, obj = resolve_qualname(module, qualname)
    if name is None or not inspect.isfunction(obj):
        return None

    if not (owner is module or (isinstance(owner, type) and issubclass(owner, Traitable))):
        return None  #-- some other class, e.g. third-party code reached transitively

    return (owner, name, obj)


#------------------------------------------------------------------
# current-best version + registration -- shared by both warning kinds, so a function
# discovered via one warning kind composes onto a fix already applied via the other,
# regardless of which order the two warnings happen to be discovered in
#------------------------------------------------------------------

def _current_version(owner, name: str, original):
    if isinstance(owner, type) and issubclass(owner, Traitable):
        trait_name = name[:-len('_get')] if name.endswith('_get') else None
        trait = owner.s_dir.get(trait_name) if trait_name else None
        if trait is not None and trait.f_get_edt is not None:
            return trait.f_get_edt
        alt_methods = EdgeDepsTracker.s_instrumented_classes.get(owner, {})
        return alt_methods.get(name, original)

    alt_funcs = EdgeDepsTracker.s_instrumented_modules.get(getattr(owner, '__name__', None), {})
    return alt_funcs.get(name, original)


def _register(owner, name: str, alt):
    if isinstance(owner, type) and issubclass(owner, Traitable):
        trait_name = name[:-len('_get')] if name.endswith('_get') else None
        trait = owner.s_dir.get(trait_name) if trait_name else None
        if trait is not None:
            trait.set_f_get_edt(alt)
            return
        EdgeDepsTracker.s_instrumented_classes.setdefault(owner, {})[name] = alt
        return

    #-- owner is the module itself (Tier 2, reached without ever being explicitly marked)
    EdgeDepsTracker.s_instrumented_modules.setdefault(owner.__name__, {})[name] = alt


#------------------------------------------------------------------
# IBOOL2BOOL / IDOUBLE2BOOL -- a branch decision needs if_wrapper
#------------------------------------------------------------------

def instrument_from_ibool_warning(file: str, line: int) -> bool:
    """
    For a passive warning of kind IBOOL2BOOL/IDOUBLE2BOOL: resolve file:line to the function
    containing that branch and give it an if_wrapper-instrumented alt version, composed onto
    whatever's already there. Returns True if something was (re)instrumented, False if this
    location couldn't be structurally reached (out of scope / unresolvable).
    """
    target = _resolve_target(file, line)
    if target is None:
        return False
    owner, name, obj = target

    current = _current_version(owner, name, obj)
    alt = EdgeDepsTracker.IfRewriter.instrument_function(current)
    _register(owner, name, alt)
    return True


#------------------------------------------------------------------
# IDOUBLE2DOUBLE / IDOUBLE2INT / IDOUBLE2UINT / IDOUBLE_PTR2DOUBLE_PTR -- activeness lost via
# an un-AADC-aware math/builtin call
#------------------------------------------------------------------

_AADC_MATH_NAMES = {
    n for n in vars(aadc.math)
    if not n.startswith('_') and hasattr(math, n)
}


class _CallRewriter(ast.NodeTransformer):
    """
    Rewrites every eligible math.<name>(...)/abs(...)/min(...)/max(...) call to its aadc.math
    equivalent -- trivialist, like IfRewriter: once a function is being regenerated anyway,
    there's no cost to covering every eligible call in it, not just the one the warning
    happened to name (aadc.math functions are drop-in replacements, correct for passive
    inputs too). Does NOT yet handle `from math import sqrt`-style direct imports -- only the
    `math.sqrt(...)` attribute-call form.
    """

    def visit_Call(self, node: ast.Call) -> ast.Call:
        self.generic_visit(node)
        func = node.func
        if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                and func.value.id == 'math' and func.attr in _AADC_MATH_NAMES):
            node.func = self._aadc_math_attr(func.attr)
        elif (isinstance(func, ast.Name) and func.id in ('abs', 'min', 'max')
                and func.id in _AADC_MATH_NAMES):
            node.func = self._aadc_math_attr(func.id)
        return node

    @staticmethod
    def _aadc_math_attr(name: str) -> ast.Attribute:
        return ast.Attribute(
            value = ast.Attribute(value = ast.Name(id = 'aadc', ctx = ast.Load()), attr = 'math', ctx = ast.Load()),
            attr = name, ctx = ast.Load(),
        )

    @classmethod
    def instrument_function(cls, func):
        filename = inspect.getsourcefile(func) or '<unknown>'
        source_lines, start_lineno = inspect.getsourcelines(func)
        source = textwrap.dedent(''.join(source_lines))
        tree = ast.parse(source)
        ast.increment_lineno(tree, start_lineno - 1)
        func_def = tree.body[0]
        func_def.decorator_list = []
        cls().visit(func_def)
        ast.fix_missing_locations(tree)

        alt_globals = func.__globals__
        alt_globals.setdefault('aadc', aadc)
        code = compile(tree, filename, 'exec')
        exec(code, alt_globals)  # noqa: S102 -- deliberate, mirrors IfRewriter.instrument_function
        return alt_globals[func.__name__]


def instrument_from_idouble_warning(file: str, line: int) -> bool:
    """
    For a passive warning of kind IDOUBLE2DOUBLE/IDOUBLE2INT/IDOUBLE2UINT/
    IDOUBLE_PTR2DOUBLE_PTR: resolve file:line to the function containing the offending call
    and give it a _CallRewriter-instrumented alt version, composed onto whatever's already
    there. Returns True if something was (re)instrumented, False otherwise.
    """
    target = _resolve_target(file, line)
    if target is None:
        return False
    owner, name, obj = target

    current = _current_version(owner, name, obj)
    alt = _CallRewriter.instrument_function(current)
    _register(owner, name, alt)
    return True
