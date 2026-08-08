import aadc
from aadc import idouble
from aadc.evaluate_wrappers import evaluate_kernel
from core_10x.exec_control import BTP, GRAPH_ON
from core_10x.global_cache import cache
from core_10x.traitable import BoundTrait, Traitable

from xxfin.jit_aadc.aadc_context import AADCContext
from xxfin.mkt_quotable import MktDeps
from xxfin.xxfin_env_vars import XXFinEnvVars


class AadcKernel:
    @classmethod
    @cache
    def _init(cls):
        aadc_license = XXFinEnvVars.aadc_license
        if aadc_license:
            aadc.license(aadc_license)

    def __init__(self, bound_trait: BoundTrait, graph: BTP = None):
        self._init()
        self.bound_trait = bound_trait
        self.graph = graph
        self.py_res = None
        self.kernel = None
        self.input_handles = {}
        self.inputs = {}
        self.output = None
        self.deps = {}


    def build(self):
        if self.graph is None:
            self.graph = GRAPH_ON()

        bound_trait = self.bound_trait
        obj: Traitable = bound_trait.obj
        with self.graph:
            self.py_res = obj.get_trait_value(bound_trait.trait)

            mkt_deps = MktDeps(self.graph, bound_trait)
            aadc_ctx = AADCContext()
            with aadc_ctx as kernel:
                self.kernel = kernel
                self.input_handles = input_handles = {}
                self.inputs = inputs = {}
                for cls, obj_id, trait, value in mkt_deps.deps(objects = False):
                    iq = idouble(value)
                    mkt_deps.perturb(cls, obj_id, trait, iq)
                    h = iq.mark_as_input()
                    input_handles[(cls, obj_id)] = h
                    inputs[h] = value

                res_active = obj.get_trait_value(bound_trait.trait)
                self.output = res_active.mark_as_output()

            self.deps = {self.output: list(input_handles.values())}

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

    def eval(self, market_values: dict = None):
        """
        market_values: optional {(cls, quotable_id): value} overriding the values recorded at build()
        time -- obj_id/cls match the keys of self.input_handles. Falls back to the recorded
        values for any handle not overridden. A value may be a scalar or an array/sequence of
        scalars -- if any override is array-valued, the kernel evaluates one pass per element
        (all array-valued overrides must be the same length).

        Returns the computed value of the target trait -- a scalar, e.g., price, or an array if a batched
        override was used.
        """
        inputs = self._resolve_inputs(market_values)
        result = evaluate_kernel(self.kernel, {self.output: []}, inputs, 1)
        return self._unwrap(result.values[self.output])

    def eval_with_adjoints(self, market_values: dict = None, adjoints: list = None) -> tuple:
        """
        Like eval(), but also computes and returns d(output)/d(quote) for the requested market
        dependencies.

        adjoints: optional subset of self.input_handles' keys ({(cls, quotable_id), ...}) to
        compute derivatives for. Defaults to every discovered market dependency.

        Returns (value, adjoints_by_key), where adjoints_by_key is {(cls, quotable_id): derivative},
        and both value and each derivative are scalars, or arrays if a batched market_values
        override was used.
        """
        inputs = self._resolve_inputs(market_values)

        adjoint_keys = list(self.input_handles) if adjoints is None else list(adjoints)
        handles = [self._lookup_handle(key) for key in adjoint_keys]

        result = evaluate_kernel(self.kernel, {self.output: handles}, inputs, 1)
        value = self._unwrap(result.values[self.output])

        derivs_by_handle = result.derivs[self.output]
        adjoints_by_key = {key: self._unwrap(derivs_by_handle[h]) for key, h in zip(adjoint_keys, handles)}
        return (value, adjoints_by_key)
