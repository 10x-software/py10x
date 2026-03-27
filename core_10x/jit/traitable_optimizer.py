from __future__ import annotations

from core_10x.traitable import Traitable, Trait, T, RT
from core_10x.named_constant import NamedConstant
from core_10x.global_cache import cache

from core_10x.jit.traitable_method_optimizer import TraitableMethodOptimizer
from core_10x.jit.trait_getter_cython_compiler import CythonCompiler


class TraitableOptimizer:
    GENERAL_PY  = TraitableMethodOptimizer
    CYTHON_TCC  = CythonCompiler
    NUMBA       = TraitableMethodOptimizer
    AADT        = TraitableMethodOptimizer

    @staticmethod
    def optimize(traitable_class: type[Traitable], attr_name: str, mt: type[TraitableMethodOptimizer]) -> tuple[bool, TraitableMethodOptimizer]:
        topt = TraitableOptimizer.instance(traitable_class)
        op_obj = topt.apply(attr_name, mt)
        op_method = op_obj.optimized_method
        return (bool(op_method), op_obj)

    @staticmethod
    @cache
    def instance(traitable_class: type[Traitable]) -> TraitableOptimizer:
        return TraitableOptimizer(traitable_class)

    def __init__(self, traitable_class: type[Traitable]):
        self.traitable_class = traitable_class
        self.optimizers_by_attr_name: dict[str, dict] = {}

    def apply(self, attr_name: str, mt: type[TraitableMethodOptimizer]) -> TraitableMethodOptimizer:
        all_optimizers = self.optimizers_by_attr_name
        optimizers = all_optimizers.setdefault(attr_name, {})
        op_obj = optimizers.get(mt)
        if op_obj is None:
            op_class: type[TraitableMethodOptimizer] = mt
            op_obj: TraitableMethodOptimizer = op_class(self.traitable_class, attr_name, _kaboom = False)
            optimizers[mt] = op_obj

            op_method = op_obj.optimize()
            if op_method:
                trait = op_obj.trait
                if trait:
                    trait.set_f_get(op_method, True)
                else:
                    setattr(self.traitable_class, attr_name, op_method)

        return op_obj
