from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from py10x_kernel import BTraitableClass

    from core_10x.trait import Trait

# ===================================================================================================================================
#
#   age = LT(value)
#   name = 'Sasha'      #-- name = EQ('Sasha')
#   weight = BETWEEN(170, 180, bounds = (True, False)
#   weight =
# ===================================================================================================================================


# fmt: off
class _mongo_label:
    EQ      = '$eq'
    NE      = '$ne'
    GT      = '$gt'
    GE      = '$gte'
    LT      = '$lt'
    LE      = '$lte'
    IN      = '$in'
    NIN     = '$nin'
    REGEX   = '$regex'
    AND     = '$and'
    OR      = '$or'
    #NOT     = '$not'
# fmt: on

LABEL = _mongo_label


class _filter(ABC):
    @abstractmethod
    def eval(self, left_value) -> bool: ...
    @abstractmethod
    def prefix_notation(self, trait: Trait = None, traitable_class: BTraitableClass = None) -> dict: ...


class Op(_filter, ABC):
    label = ''

    def __init_subclass__(cls, label: str = None):
        if label is None:
            label = getattr(LABEL, cls.__name__)
        cls.label = label

    def __new__(cls, expression=None):
        obj = super().__new__(cls)
        obj.right_value = expression
        return obj

    def serialize_right_value(self, trait: Trait = None, traitable_class: BTraitableClass = None) -> dict:
        return trait.serialize_value(self.right_value, replace_xnone=True) if trait and traitable_class else self.right_value

    def prefix_notation(self, trait: Trait = None, traitable_class: BTraitableClass = None) -> dict:
        # noinspection PyTypeChecker
        return {self.label: self.serialize_right_value(trait, traitable_class)}


class NOT_EMPTY(Op, label=''):
    def prefix_notation(self, trait: Trait = None, traitable_class: BTraitableClass = None) -> dict:
        raise NotImplementedError

    def eval(self, left_value) -> bool:
        return bool(left_value)


class EQ(Op):
    def eval(self, left_value) -> bool:
        return left_value == self.right_value


class NE(Op):
    def eval(self, left_value) -> bool:
        return left_value != self.right_value


class GT(Op):
    def eval(self, left_value) -> bool:
        return left_value > self.right_value


class GE(Op):
    def eval(self, left_value) -> bool:
        return left_value >= self.right_value


class LT(Op):
    def eval(self, left_value) -> bool:
        return left_value < self.right_value


class LE(Op):
    def eval(self, left_value) -> bool:
        return left_value <= self.right_value


class IN(Op):
    def __new__(cls, values: list | tuple):
        assert isinstance(values, list) or isinstance(values, tuple), f'{cls.__name__}() requires a list or tuple'
        return super().__new__(cls, values)

    def serialize_right_value(self, trait: Trait = None, traitable_class: BTraitableClass = None) -> dict:
        return [trait.serialize_value(value, replace_xnone=True) for value in self.right_value] if trait and traitable_class else self.right_value

    def eval(self, left_value) -> bool:
        return left_value in self.right_value


class NIN(IN):
    def eval(self, left_value) -> bool:
        return left_value not in self.right_value


# class REGEX(Op):


class BETWEEN(Op, label=''):
    def __new__(cls, a, b, bounds=(True, True)):
        obj = super().__new__(cls)
        assert isinstance(bounds, tuple) and len(bounds) == 2, f'{cls.__name__} - (bool, bool) is expected for bounds'

        bound_a, bound_b = bounds
        obj.left = GE(a) if bound_a else GT(a)
        obj.right = LE(b) if bound_b else LT(b)
        return obj

    def eval(self, left_value) -> bool:
        return self.left.eval(left_value) and self.right.eval(left_value)

    def prefix_notation(self, trait: Trait = None, traitable_class: BTraitableClass = None) -> dict:
        res = self.left.prefix_notation(trait, traitable_class)
        res.update(self.right.prefix_notation(trait, traitable_class))
        return res


class BoolOp(Op, ABC, label=''):
    s_false: IN = IN([])

    @classmethod
    def _simplify(cls, expressions: tuple, false: IN) -> list: ...

    def __new__(cls, *expressions):
        expressions = cls._simplify(expressions, cls.s_false)
        if len(expressions) == 1:
            return expressions[0]

        obj = super().__new__(cls, expressions)
        return obj

    def prefix_notation(self, trait: Trait = None, traitable_class: BTraitableClass = None) -> dict:
        rvalues = [pn for e in self.right_value if (pn := e.prefix_notation(trait, traitable_class))]
        return {self.label: rvalues} if rvalues else {}


class AND(BoolOp):
    @classmethod
    def _simplify(cls, expressions, false):
        return [false] if false in expressions else expressions

    def eval(self, left_value) -> bool:
        return all(e.eval(left_value) for e in self.right_value)


class OR(BoolOp):
    @classmethod
    def _simplify(cls, expressions, false):
        expressions = [expression for expression in expressions if expression is not false]
        return [false] if not expressions else expressions

    def eval(self, left_value) -> bool:
        return any(e.eval(left_value) for e in self.right_value)


class f(_filter):
    def __init__(self, _f: _filter = None, _t: BTraitableClass = None, **named_expressions):
        self.filter = _f
        self.traitable_class = _t
        self.named_expressions = {
            name: expression if isinstance(expression, _filter) else EQ(expression) for name, expression in named_expressions.items()
        }

    def eval(self, traitable_or_dict) -> bool:
        if self.filter:
            if not self.filter.eval(traitable_or_dict):
                return False

        return all(item.eval(traitable_or_dict[name]) for name, item in self.named_expressions.items())

    def prefix_notation(self, trait: Trait = None, traitable_class: BTraitableClass = None) -> dict:
        traitable_class = traitable_class or self.traitable_class
        trait_dir = traitable_class.trait_dir() if traitable_class else {}
        clause = {name: pn for name, item in self.named_expressions.items() if (pn := item.prefix_notation(trait_dir.get(name), traitable_class))}
        if self.filter:
            filter_clause = self.filter.prefix_notation(traitable_class=traitable_class)
            clause = {AND.label: [filter_clause, clause]} if clause else filter_clause

        return clause
