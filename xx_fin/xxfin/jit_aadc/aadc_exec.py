from __future__ import annotations

from typing import Any

from aadc import idouble, ibool
from aadc.evaluate_wrappers import evaluate_kernel

from core_10x.edge_deps_tracker import EdgeDepsTracker
from core_10x.exec_control import BoundTrait, GRAPH_ON, BTP
from core_10x.traitable import Traitable, Trait

from xxfin.mkt_quotable import MktDeps
from xxfin.jit_aadc.aadc_context import AADCContext

class AadcKernel:
    def __init__(self, obj: Traitable, trait: Trait):
        self.obj = obj
        self.trait = trait
        self.py_res = None
        self.kernel = None
        self.input_handles = {}
        self.inputs = {}
        self.output = None
        self.deps = {}
        self.exec_path_handles = {}

    def build(self, mkt_deps: MktDeps, tracker: EdgeDepsTracker, compile_kernel: bool = False):
        """compile_kernel: extra time here for faster eval()/eval_with_adjoints() -- worth it when
        the kernel will be replayed many times, not for a single valuation."""

        aadc_ctx = AADCContext()
        with aadc_ctx as kernel:
            self.kernel = kernel
            self.input_handles = input_handles = {}
            self.inputs = inputs = {}
            for cls, obj_id, trait, value in mkt_deps.deps(objects = False):
                iq = idouble(value)
                mkt_deps.perturb(cls, obj_id, trait, iq)
                h = iq.mark_as_input()
                # TODO: key drops `trait` -- collides if target_class ever has >1 leaf trait
                input_handles[(cls, obj_id)] = h
                inputs[h] = value

            tracker.clear_if_wrappers_log()
            res_active = self.obj.get_trait_value(self.trait)
            self.output = res_active.mark_as_output()

        self.exec_path_handles = exec_path_handles = {}
        for (guard_id, condition) in tracker.if_wrappers_log:
            if type(condition) is ibool:
                key = (guard_id, bool(condition))
                if key not in exec_path_handles:
                    exec_path_handles[key] = condition.mark_as_output()

        self.deps = {self.output: list(input_handles.values())}

        if compile_kernel:
            self.kernel.compile()

    def _lookup_handle(self, key):
        h = self.input_handles.get(key)
        if h is None:
            raise ValueError(f'Unknown market dependency {key}')
        return h

    def _resolve_inputs(self, market_values: dict = None) -> dict:
        inputs = self.inputs
        if market_values:
            inputs = dict(inputs)
            for key, value in market_values.items():
                inputs[self._lookup_handle(key)] = value
        return inputs

    @staticmethod
    def _unwrap(arr):
        return arr.item() if arr.size == 1 else arr

    # def eval_with_adjoints(self, market_values: dict = None, adjoints: list = None) -> tuple:
    #     """
    #     Like eval(), but also computes and returns d(output)/d(quote) for the requested market
    #     dependencies.
    #
    #     adjoints: optional subset of self.input_handles' keys ({(cls, quotable_id), ...}) to
    #     compute derivatives for. Defaults to every discovered market dependency.
    #
    #     Returns (value, adjoints_by_key), where adjoints_by_key is {(cls, quotable_id): derivative},
    #     and both value and each derivative are scalars, or arrays if a batched market_values
    #     override was used.
    #     """
    #     inputs = self._resolve_inputs(market_values)
    #
    #     adjoint_keys = list(self.input_handles) if adjoints is None else list(adjoints)
    #     handles = [self._lookup_handle(key) for key in adjoint_keys]
    #
    #     result = evaluate_kernel(self.kernel, {self.output: handles}, inputs, 1)
    #     value = self._unwrap(result.values[self.output])
    #
    #     derivs_by_handle = result.derivs[self.output]
    #     adjoints_by_key = {key: self._unwrap(derivs_by_handle[h]) for key, h in zip(adjoint_keys, handles)}
    #     return (value, adjoints_by_key)

class AadcExec:

    def __init__(self, bound_trait: BoundTrait, graph: BTP = None):
        if graph is None:
            graph = GRAPH_ON()

        self.bound_trait = bound_trait
        self.graph = graph
        self.edt_tracker: EdgeDepsTracker = None
        self.kernels = {}

    def __enter__(self):
        #-- Monkey-patch ONCE, for AadcExec's whole life -- not per eval() call
        self.edt_tracker = EdgeDepsTracker()
        self.edt_tracker.__enter__()
        self.graph.__enter__()
        return self

    def __exit__(self, *args):
        self.graph.__exit__(*args)
        self.edt_tracker.__exit__(*args)
        self.edt_tracker = None

    def create_kernel(self) -> tuple[AadcKernel, Any]:
        obj: Traitable = self.bound_trait.obj
        trait: Trait = self.bound_trait.trait
        tracker = self.edt_tracker
        with self.graph as graph:
            tracker.clear_if_wrappers_log()
            py_res = obj.get_trait_value(trait)
            signature = self.edt_tracker.execution_path()

            all_kernels = self.kernels
            kernel = all_kernels.get(signature)
            if not kernel:
                mkt_deps = MktDeps(graph, self.bound_trait)
                kernel = AadcKernel(obj, trait)
                kernel.build(mkt_deps, self.edt_tracker, compile_kernel = False)
                all_kernels[signature] = kernel

            return (kernel, py_res)

    def eval_kernel(self, kernel: AadcKernel, market_values: dict = None) -> tuple[bool, Any]:
        """
        market_values: optional {(cls, quotable_id): value} overriding the values recorded at build()
        time -- obj_id/cls match the keys of self.input_handles. Falls back to the recorded
        values for any handle not overridden. A value may be a scalar or an array/sequence of
        scalars -- if any override is array-valued, the kernel evaluates one pass per element
        (all array-valued overrides must be the same length).

        Returns: (True, the computed value of the target trait -- a scalar, e.g., price, or an array if a batched override was used)
                or (False, None) if the kernel's exec path does not match the recorded one (i.e., Edge Dependencies changed)
        """
        inputs = kernel._resolve_inputs(market_values)
        exec_path_handles = list(kernel.exec_path_handles.values())

        request = {kernel.output: [], **{h: [] for h in exec_path_handles}}
        result = evaluate_kernel(kernel.kernel, request, inputs, 1)

        still_valid = all(
            bool(kernel._unwrap(result.values[h])) == outcome
            for (guard_id, outcome), h in kernel.exec_path_handles.items()
        )
        if not still_valid:
            return (False, None)

        return (True, kernel._unwrap(result.values[kernel.output]))