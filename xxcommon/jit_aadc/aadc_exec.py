from __future__ import annotations

import ast
import linecache
import math
from typing import Any

import aadc
from aadc import aadc_assert, idouble, ibool, iint, ErrorCollectionMode, record_kernel
from aadc.evaluate_wrappers import evaluate_kernel

from core_10x.exec_control import BoundTrait, GraphDeps, GRAPH_ON, BTP
from core_10x.callable_instrumentation import CallableRewriter, InstrumentationRegistry
from core_10x.traitable import Traitable, Trait

from xxcommon.jit_aadc.aadc_context import AADCDomainSwap


AADC_ACTIVE_TYPES = {idouble, ibool, iint}


class AadcCallableRewriter(CallableRewriter):
    """
    aadc_exec's theme -- wraps every `if` test in a call to if_wrapper (AadcExec.if_guard), and redirects every
    eligible math.*/abs/min/max call to call_target (aadc.math). Both trivialist, unfiltered: once a function's
    source is being regenerated at all, there's no marginal cost to covering everything eligible in the same pass.
    """

    IF_WRAPPER_NAME  = '__if_wrapper__'
    CALL_TARGET_NAME = '__call_target__'

    def __init__(self, if_wrapper, call_names: set[str], call_target):
        super().__init__()
        self.call_names = call_names
        self.globals_to_bind[self.IF_WRAPPER_NAME] = if_wrapper
        self.globals_to_bind[self.CALL_TARGET_NAME] = call_target

    def visit_If(self, node: ast.If) -> ast.If:
        self.generic_visit(node)
        node.test = ast.Call(
            func = ast.Name(id = self.IF_WRAPPER_NAME, ctx = ast.Load()),
            args = [ast.Constant(value = self.location_id(node)), node.test],
            keywords = [],
        )
        return node

    def visit_Call(self, node: ast.Call) -> ast.Call:
        self.generic_visit(node)
        func = node.func
        if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                and func.value.id == 'math' and func.attr in self.call_names):
            node.func = self._target_attr(func.attr)
        elif isinstance(func, ast.Name) and func.id in self.call_names:
            node.func = self._target_attr(func.id)
        return node

    def _target_attr(self, name: str) -> ast.Attribute:
        return ast.Attribute(value = ast.Name(id = self.CALL_TARGET_NAME, ctx = ast.Load()), attr = name, ctx = ast.Load())


#-- names present in both aadc.math and stdlib math -- the eligible set for call redirection
AADC_MATH_NAMES = { n for n in vars(aadc.math) if not n.startswith('_') and hasattr(math, n) }


class AadcKernel:
    def __init__(self, obj: Traitable, trait: Trait):
        self.obj = obj
        self.trait = trait
        self.kernel = None
        self.deps: GraphDeps = None
        self.input_handles = {}
        self.output = None

    def build(self, deps: GraphDeps):
        self.deps = deps
        with record_kernel() as kernel:
            self.kernel = kernel
            self.input_handles = input_handles = {}
            for cls, obj_id, trait, value in deps.deps(objects = False):
                iq = idouble(value)
                deps.perturb(cls, obj_id, trait, iq)
                h = iq.mark_as_input()
                input_handles[(cls, obj_id, trait)] = h

            #-- if_guard()'s aadc_assert calls fire inline, during this call, as each instrumented
            # `if` is reached -- nothing further needed here for staleness-checking.
            res_active = self.obj.get_trait_value(self.trait)
            self.output = res_active.mark_as_output()

    def _resolve_inputs(self) -> dict:
        #-- reads each input's current value straight off the graph node deps.perturb() set at build
        # time -- picks up any plain `obj.trait = value` mutation done on that same node since, live.
        cache = self.deps.gp.cache()
        read = cache.read_existing_node
        inputs = {}
        for (cls, obj_id, trait), handle in self.input_handles.items():
            value = read(cls.s_bclass, obj_id, trait)
            inputs[handle] = value.val() if type(value) in AADC_ACTIVE_TYPES else value
        return inputs

    @staticmethod
    def _unwrap(arr):
        return arr.item() if arr.size == 1 else arr


class AadcExec:
    s_current_log: set | None = None   #-- class attribute, single global slot -- see if_guard()

    def __init__(self, bound_trait: BoundTrait, target_class: type, *target_trait_names: str, graph: BTP = None):
        self.bound_trait = bound_trait
        self.target_class = target_class
        self.target_trait_names = target_trait_names
        self.graph = graph if graph is not None else GRAPH_ON()
        self.kernels: dict[frozenset, AadcKernel] = {}

    def __enter__(self):
        _registry.apply()      #-- activate whatever's already been built via auto-instrumentation
        # at import time (see module-level _registry.enable_auto_instrumentation() below) --
        # apply()/restore() only toggle activation, they never build anything themselves.
        self._domain_swap = AADCDomainSwap()
        self._domain_swap.__enter__()
        self.graph.__enter__()
        return self

    def __exit__(self, *args):
        self.graph.__exit__(*args)
        self._domain_swap.__exit__(*args)
        _registry.restore()

    @classmethod
    def if_guard(cls, guard_id: str, condition):
        """AST-rewritten call site: `if AadcExec.if_guard('file:line', x > 5.0): ...`"""
        is_active = type(condition) in AADC_ACTIVE_TYPES
        if aadc.is_recording() and is_active:
            outcome = condition.val()
            aadc_assert(condition if outcome else ~condition, guard_id)
            return outcome

        outcome = condition.val() if is_active else condition
        if cls.s_current_log is not None:
            cls.s_current_log.add((guard_id, outcome))
        return outcome

    def create_kernel(self) -> tuple[AadcKernel, Any]:
        obj, trait = self.bound_trait.obj, self.bound_trait.trait
        with self.graph as graph:
            AadcExec.s_current_log = set()
            py_res = obj.get_trait_value(trait)          #-- 2.1: graph + signature, one call
            signature = frozenset(AadcExec.s_current_log)
            AadcExec.s_current_log = None

            kernel = self.kernels.get(signature)
            if kernel is None:                            #-- 2.2: miss -> build
                deps = GraphDeps(graph, self.bound_trait, self.target_class, *self.target_trait_names)
                kernel = AadcKernel(obj, trait)
                kernel.build(deps)

                warnings = kernel.kernel.passive_warnings()
                if warnings:
                    raise_uninstrumented_warning(warnings[0])

                self.kernels[signature] = kernel

            return (kernel, py_res)

    def eval_kernel(self, kernel: AadcKernel) -> tuple[bool, Any]:
        inputs = kernel._resolve_inputs()
        result = evaluate_kernel(
            kernel.kernel, {kernel.output: []}, inputs, 1,
            error_mode = ErrorCollectionMode.ERRORS_ONLY,
        )
        if result.errors.has_errors():
            return (False, None)                          #-- caller: go back to create_kernel()
        return (True, kernel._unwrap(result.values[kernel.output]))


#-- DefLocator exists SOLELY to make raise_uninstrumented_warning's message name the offending function ("...in
# Widget.label_get") instead of a bare file:line -- purely a diagnostic-quality nicety, not load-bearing: the
# warning is just as actionable (file:line alone is enough to find it) without this. Grouped here since
# raise_uninstrumented_warning is its only consumer.
class DefLocator(ast.NodeVisitor):
    """
    Finds the dotted qualname of the innermost def (function, method, or nested closure) containing a given
    line. AST-based (source text only), not object-graph scanning: a closure only exists as a live object
    during its enclosing call, so scanning for a matching code object after the fact would silently match
    the wrong (outer) function instead.
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


def raise_uninstrumented_warning(w: dict):
    file, line, kind_name = w['file'], w['line'], w['kind_name']
    qualname = DefLocator.find(file, line) or '<unresolved>'
    raise RuntimeError(
        f"AADC recording hit an uninstrumented passive warning ({kind_name}) "
        f"at {file}:{line}, in {qualname}.\n"
        f"Possible reasons:\n"
        f"  - Traitable subclass not covered by the registered base-class list.\n"
        f"  - Project module not marked for instrumentation.\n"
        f"  - Foreign module not listed in the registry.\n"
        f"Fix: add the relevant class/module to the registry, then rebuild."
    )


_registry = InstrumentationRegistry(
    AadcCallableRewriter(
        if_wrapper = AadcExec.if_guard,
        call_names = AADC_MATH_NAMES,
        call_target = aadc.math,
    )
)
_registry.enable_auto_instrumentation()
