from __future__ import annotations

import inspect
import typing
from typing import Callable

from core_10x.global_cache import cache
from core_10x.traitable import Traitable, Trait

class MethodOptimizationRecord:
    def __init__(self, py_method: Callable, _kaboom = True):
        if _kaboom:
            raise AssertionError(f'Must call {self.__class__.__name__}.instance() instead')

        self.original_method = py_method
        self.optimized_methods: dict[type[TraitableMethodOptimizer], Callable] = {}
        self.best: type[TraitableMethodOptimizer] = None

    def add_optimization(self, op_obj: TraitableMethodOptimizer):
        op_class = op_obj.__class__
        self.optimized_methods[op_class] = op_obj.optimized_method

    def set_best(self, op_class: type[TraitableMethodOptimizer]):
        if not op_class in self.optimized_methods:
            raise AssertionError(f'Cannot set {op_class} as the best optimization as the optimized method is missing')
        self.best = op_class

    def get_best_optimization(self) -> tuple[type[TraitableMethodOptimizer], Callable]:
        best = self.best
        return (best, self.optimized_methods.get(best)) if best else (None, None)

    def get_optimization(self, op_class_or_obj) -> Callable:
        if isinstance(op_class_or_obj, TraitableMethodOptimizer):
            op_class_or_obj = op_class_or_obj.__class__
        return self.optimized_methods.get(op_class_or_obj)

    def get_original_method(self) -> Callable:
        return self.original_method

    @staticmethod
    @cache
    def instance(py_method: Callable) -> MethodOptimizationRecord:
        return MethodOptimizationRecord(py_method, _kaboom = False)

class TraitableMethodData:
    @staticmethod
    @cache
    def record(traitable_class: type[Traitable], attr_name: str) -> TraitableMethodData:
        return TraitableMethodData(traitable_class, attr_name, _kaboom = False)

    def __init__(self, traitable_class: type[Traitable], attr_name: str, _kaboom = True):
        if _kaboom:
            raise AssertionError(f'Must call {self.__class__.__name__}.instance() instead')

        if not inspect.isclass(traitable_class) or not issubclass(traitable_class, Traitable):
            raise AssertionError('traitable_class must be a subclass of Traitable')

        attr = getattr(traitable_class, attr_name, None)
        if attr is None:
            raise AssertionError(f'{traitable_class} - unknown attribute {attr_name}')

        if isinstance(attr, Trait):
            trait = attr
            original_method = attr.custom_f_get()
            has_params = bool(attr.getter_params)
            return_type = attr.data_type
        else:   #-- must be a method
            if not callable(attr):
                raise AssertionError(f'{traitable_class.__name__}.{attr_name} - must be a method')

            trait = None
            original_method = attr
            hints = typing.get_type_hints(original_method)
            return_type = hints.get('return')
            n = len(inspect.signature(original_method).parameters)
            has_params = n > 1  #-- self doesn't count

        self.traitable_class = traitable_class
        self.name = attr_name
        self.trait = trait
        self.original_method = original_method
        self.has_params = has_params
        self.return_type = return_type

class TraitableMethodOptimizer:
    @staticmethod
    @cache
    def optimization_record(traitable_class: type[Traitable], attr_name: str) -> MethodOptimizationRecord:
        data = TraitableMethodData.record(traitable_class, attr_name)
        return MethodOptimizationRecord.instance(data.original_method)

    @classmethod
    def is_lazy(cls) -> bool:
        return False

    def __init__(self, traitable_class: type[Traitable], attr_name: str):
        self.data = data = TraitableMethodData.record(traitable_class, attr_name)
        op_rec = MethodOptimizationRecord.instance(data.original_method)
        self.optimized_method = op_rec.get_optimization(self.__class__)

    def optimize(self) -> Callable:
        op_method = self.optimized_method
        if op_method is None:
            original_method = self.data.original_method
            if original_method is not None:
                op_method = self.generate_optimized_method()
                self.optimized_method = op_method
                op_rec = MethodOptimizationRecord.instance(original_method)
                op_rec.add_optimization(self)

        return op_method

    def generate_optimized_method(self) -> Callable:
        raise NotImplementedError
