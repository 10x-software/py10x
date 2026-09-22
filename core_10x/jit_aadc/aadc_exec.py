from __future__ import annotations

import ast
import linecache
import math
from typing import Any

import aadc
from aadc import aadc_assert, idouble, ibool, iint, ErrorCollectionMode
from aadc.evaluate_wrappers import evaluate_kernel

from core_10x.exec_control import BoundTrait, GRAPH_ON, BTP
from core_10x.callable_instrumentation import CallableRewriter, InstrumentationRegistry
from core_10x.traitable import Traitable, Trait

from core_10x.jit_aadc.aadc_context import AADCContext
from xxfin.mkt_quotable import MktDeps


class DefLocator(ast.NodeVisitor):
    """
    Finds the dotted qualname of the innermost def (function, method, or nested closure)
    containing a given line -- used to name the function in UninstrumentedAadcWarning's
    message. AST-based (source text only), not object-graph scanning: a closure only exists
    as a live object during its enclosing call, so scanning for a matching code object after
    the fact would silently match the wrong (outer) function instead.
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


class AadcCallableRewriter(CallableRewriter):
    """
    aadc_exec's theme -- wraps every `if` test in a call to if_wrapper (AadcExec.guard), and
    redirects every eligible math.*/abs/min/max call to call_target (aadc.math). Both
    trivialist, unfiltered: once a function's source is being regenerated at all, there's no
    marginal cost to covering everything eligible in the same pass.
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


class UninstrumentedAadcWarning(RuntimeError):
    @classmethod
    def from_warning(cls, w: dict) -> 'UninstrumentedAadcWarning':
        file, line, kind_name = w['file'], w['line'], w['kind_name']
        qualname = DefLocator.find(file, line) or '<unresolved>'
        return cls(
            f"AADC recording hit an uninstrumented passive warning ({kind_name}) "
            f"at {file}:{line}, in {qualname}.\n"
            f"Possible reasons:\n"
            f"  - Traitable subclass not covered by the registered base-class list.\n"
            f"  - Project module not marked for instrumentation.\n"
            f"  - Foreign module not listed in the registry.\n"
            f"Fix: add the relevant class/module to the registry, then rebuild."
        )


class AadcKernel:
    def __init__(self, obj: Traitable, trait: Trait):
        self.obj = obj
        self.trait = trait
        self.kernel = None
        self.input_handles = {}
        self.inputs = {}
        self.output = None

    def build(self, mkt_deps: MktDeps):
        with AADCContext() as kernel:
            self.kernel = kernel
            self.input_handles = input_handles = {}
            self.inputs = inputs = {}
            for cls, obj_id, trait, value in mkt_deps.deps(objects = False):
                iq = idouble(value)
                mkt_deps.perturb(cls, obj_id, trait, iq)
                h = iq.mark_as_input()
                input_handles[(cls, obj_id)] = h   #-- TODO: still drops `trait`
                inputs[h] = value

            #-- guard()'s aadc_assert calls fire inline, during this call, as each instrumented
            # `if` is reached -- nothing further needed here for staleness-checking.
            res_active = self.obj.get_trait_value(self.trait)
            self.output = res_active.mark_as_output()

    def _resolve_inputs(self, market_values: dict = None) -> dict:
        inputs = self.inputs
        if market_values:
            inputs = dict(inputs)
            for key, value in market_values.items():
                inputs[self.input_handles[key]] = value
        return inputs

    @staticmethod
    def _unwrap(arr):
        return arr.item() if arr.size == 1 else arr


class AadcExec:
    s_current_log: set | None = None   #-- class attribute, single global slot -- see guard()

    def __init__(self, bound_trait: BoundTrait, graph: BTP = None):
        self.bound_trait = bound_trait
        self.graph = graph if graph is not None else GRAPH_ON()
        self.kernels: dict[frozenset, AadcKernel] = {}

    def __enter__(self):
        _registry.apply()      #-- activate whatever's already been built via auto-instrumentation
        # at import time (see module-level _registry.enable_auto_instrumentation() below) --
        # apply()/restore() only toggle activation, they never build anything themselves.
        self.graph.__enter__()
        return self

    def __exit__(self, *args):
        self.graph.__exit__(*args)
        _registry.restore()

    @classmethod
    def guard(cls, guard_id: str, condition):
        """AST-rewritten call site: `if AadcExec.guard('file:line', x > 5.0): ...`"""
        if aadc.is_recording():
            outcome = condition.val()
            aadc_assert(condition if outcome else ~condition, guard_id)
            return outcome
        outcome = condition.val() if type(condition) in (ibool, idouble, iint) else condition
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
                mkt_deps = MktDeps(graph, self.bound_trait)
                kernel = AadcKernel(obj, trait)
                kernel.build(mkt_deps)

                warnings = kernel.kernel.passive_warnings()
                if warnings:
                    raise UninstrumentedAadcWarning.from_warning(warnings[0])

                self.kernels[signature] = kernel

            return (kernel, py_res)

    def eval_kernel(self, kernel: AadcKernel, market_values: dict = None) -> tuple[bool, Any]:
        inputs = kernel._resolve_inputs(market_values)
        result = evaluate_kernel(
            kernel.kernel, {kernel.output: []}, inputs, 1,
            error_mode = ErrorCollectionMode.ERRORS_ONLY,
        )
        if result.errors.has_errors():
            return (False, None)                          #-- caller: go back to create_kernel()
        return (True, kernel._unwrap(result.values[kernel.output]))


_registry = InstrumentationRegistry(
    AadcCallableRewriter(
        if_wrapper = AadcExec.guard,
        call_names = AADC_MATH_NAMES,
        call_target = aadc.math,
    )
)
_registry.enable_auto_instrumentation()
