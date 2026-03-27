from __future__ import annotations

import inspect
import typing

from core_10x.traitable import Traitable, Trait

class TraitableMethodOptimizer:
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

        self.optimized_method = None

    def optimize(self) -> typing.Callable:
        op_method = self.optimized_method
        if op_method is None:
            original_method = self.original_method
            if original_method is not None:
                op_method = self.generate_optimized_method()
                self.optimized_method = op_method

        return op_method

    def generate_optimized_method(self) -> typing.Callable:
        raise NotImplementedError
