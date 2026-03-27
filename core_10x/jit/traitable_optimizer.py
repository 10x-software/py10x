from __future__ import annotations

from core_10x.traitable import Traitable, Trait, T, RT, XNone
from core_10x.global_cache import cache
from core_10x.logger import PerfTimer
from core_10x.xinf import XInf

from core_10x.jit.traitable_method_optimizer import TraitableMethodOptimizer
from core_10x.jit.trait_getter_cython_compiler import CythonCompiler
from core_10x.jit.trait_getter_numba_compiler import NumbaCompiler


class TraitableOptimizer:
    GENERAL_PY  = None
    CYTHON_TCC  = CythonCompiler
    NUMBA       = NumbaCompiler
    AADT        = None
    _BEST       = XNone
    s_opt_classes = { CYTHON_TCC, NUMBA }

    @staticmethod
    def optimize(test_obj: Traitable, attr_name: str, mt: type[TraitableMethodOptimizer] = XNone) -> tuple[bool, TraitableMethodOptimizer]:
        if mt is None:
            return (False, None)

        topt: TraitableOptimizer = TraitableOptimizer.instance(test_obj.__class__)
        if mt is XNone:
            op_obj = TraitableOptimizer.find_best_optimizer(test_obj, attr_name)
            if not op_obj:
                return (False, None)

        else:
            op_obj = topt.apply(attr_name, mt)

        op_method = op_obj.optimized_method
        return (bool(op_method), op_obj)

    @staticmethod
    def find_best_optimizer(test_obj: Traitable, attr_name: str, num_runs: int = 5, force = False) -> TraitableMethodOptimizer:
        topt: TraitableOptimizer = TraitableOptimizer.instance(test_obj.__class__)
        best = topt.best_optimizer(attr_name)
        if best and not force:
            return best

        best = topt.choose_optimizer(test_obj, attr_name, num_runs)
        topt._use_optimizer(best)
        return best

    @staticmethod
    @cache
    def instance(traitable_class: type[Traitable]) -> TraitableOptimizer:
        return TraitableOptimizer(traitable_class)

    def __init__(self, traitable_class: type[Traitable]):
        self.traitable_class = traitable_class
        self.optimizers_by_attr_name: dict[str, dict] = {}

    def _optimizers_by_attr(self, attr_name: str) -> dict:
        optimizers = self.optimizers_by_attr_name.setdefault(attr_name, {})
        if not optimizers:
            optimizers[TraitableMethodOptimizer] = TraitableMethodOptimizer(self.traitable_class, attr_name, _kaboom = False)   #-- No optimizer
            optimizers[XNone] = XNone    #-- slot for a 'preferred' optimizer
        return optimizers

    def apply(self, attr_name: str, mt: type[TraitableMethodOptimizer]) -> TraitableMethodOptimizer:
        optimizers = self._optimizers_by_attr(attr_name)
        op_obj = optimizers.get(mt)
        if op_obj is None:
            op_class: type[TraitableMethodOptimizer] = mt
            op_obj: TraitableMethodOptimizer = op_class(self.traitable_class, attr_name, _kaboom = False)
            optimizers[mt] = op_obj

            op_obj.optimize()
            self._use_optimizer(op_obj)

        return op_obj

    def _use_optimizer(self, op_obj: TraitableMethodOptimizer, op_method = None):
        if op_method is None:
            op_method = op_obj.optimized_method

        if op_method:
            trait = op_obj.trait
            if trait:
                trait.set_f_get(op_method, True)
            else:
                setattr(self.traitable_class, op_obj.name, op_method)

    def choose_optimizer(self, test_obj: Traitable, attr_name: str, num_runs: int) -> TraitableMethodOptimizer:
        optimizers = self._optimizers_by_attr(attr_name)
        #-- for traits ONLY for now
        results = {}
        for op_class in self.s_opt_classes:
            self.reset(attr_name)
            try:
                op_obj = self.apply(attr_name, op_class)
                op_method = op_obj.optimized_method
            except Exception as ex:
                print(f'{op_class.__name__} failed to optimize:\n')
                print(str(ex))
                continue

            if op_method:
                results[op_obj] = res = [0., 0.]

                r = test_obj.get_value(attr_name)
                res[0] = r
                with PerfTimer() as clock:
                    for i in range(num_runs):
                        test_obj.get_value(attr_name)
                dt = clock.elapsed
                res[1] = dt

        self.reset(attr_name)
        value = test_obj.get_value(attr_name)
        min_dt = XInf
        chosen_obj = None
        for op_obj, (val, elapsed) in results.items():
            if val != value:
                raise ValueError(f'{op_obj.__class__}: {val} != {value}')

            if elapsed < min_dt:
                min_dt = elapsed
                chosen_obj = op_obj

        if chosen_obj:
            optimizers[XNone] = chosen_obj

        return chosen_obj

    def best_optimizer(self, attr_name: str) -> TraitableMethodOptimizer:
        optimizers = self._optimizers_by_attr(attr_name)
        return optimizers.get(XNone)

    def reset(self, attr_name: str):
        optimizers = self._optimizers_by_attr(attr_name)
        no_opt = optimizers[TraitableMethodOptimizer]
        self._use_optimizer(no_opt, op_method = no_opt.original_method)
