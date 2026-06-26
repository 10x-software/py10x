from __future__ import annotations

import operator
from abc import ABC, abstractmethod
from functools import reduce
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from py10x_kernel import BTraitableClass
    from core_10x.traitable import Traitable

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
    def prefix_notation(self, field_name: str = None, traitable_class: BTraitableClass = None) -> dict: ...
    @abstractmethod
    def ibis(self, ibis_collection, field_name: str = None, traitable_class: BTraitableClass = None): ...


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

    def serialize_right_value(self, field_name: str, traitable_class: BTraitableClass):
        return trait.serialize_value(self.right_value, replace_xnone=True) if traitable_class and (trait := traitable_class.find_trait(field_name)) else self.right_value

    def prefix_notation(self, field_name: str=None, traitable_class: BTraitableClass=None) -> dict:
        # noinspection PyTypeChecker
        return {self.label: self.serialize_right_value(field_name, traitable_class)}

    @staticmethod
    def _eval(left, right) -> bool:
        raise NotImplementedError

    def eval(self, left_value) -> bool:
        return self._eval(left_value, self.right_value)

    def ibis(self, ibis_collection, field_name: str = None, traitable_class: BTraitableClass = None):
        trait = traitable_class.find_trait(field_name) if traitable_class and field_name else None
        col = ibis_collection.ibis_col(field_name, trait)
        right = ibis_collection.ibis_right_value(self.serialize_right_value(field_name, traitable_class))
        return self._eval(col, right)


class NOT_EMPTY(Op, label=''):
    def prefix_notation(self, field_name: str=None, traitable_class: BTraitableClass=None) -> dict:
        raise NotImplementedError

    @staticmethod
    def _eval(left, right) -> bool:
        return bool(left)

    def ibis(self, ibis_collection, field_name: str = None, traitable_class: BTraitableClass = None):
        raise NotImplementedError


class EQ(Op):
    @staticmethod
    def _eval(left, right) -> bool:
        return left == right


class NE(Op):
    @staticmethod
    def _eval(left, right) -> bool:
        return left != right


class GT(Op):
    @staticmethod
    def _eval(left, right) -> bool:
        return left > right


class GE(Op):
    @staticmethod
    def _eval(left, right) -> bool:
        return left >= right


class LT(Op):
    @staticmethod
    def _eval(left, right) -> bool:
        return left < right


class LE(Op):
    @staticmethod
    def _eval(left, right) -> bool:
        return left <= right


class IN(Op):
    def __new__(cls, values: list | tuple | set):
        assert isinstance(values, (list, tuple, set)), f'{cls.__name__}() requires a list, tuple, or set'
        return super().__new__(cls, values)

    def serialize_right_value(self, field_name: str, traitable_class: BTraitableClass):
        return [trait.serialize_value(value, replace_xnone=True) for value in self.right_value] if traitable_class and (trait := traitable_class.find_trait(field_name)) else self.right_value

    @staticmethod
    def _eval(left, right) -> bool:
        return left in right

    def ibis(self, ibis_collection, field_name: str = None, traitable_class: BTraitableClass = None):
        trait = traitable_class.find_trait(field_name) if traitable_class and field_name else None
        col = ibis_collection.ibis_col(field_name, trait)
        right = [ibis_collection.ibis_right_value(v) for v in self.serialize_right_value(field_name, traitable_class)]
        return col.isin(right)


class NIN(IN):
    @staticmethod
    def _eval(left, right) -> bool:
        return left not in right

    def ibis(self, ibis_collection, field_name: str = None, traitable_class: BTraitableClass = None):
        trait = traitable_class.find_trait(field_name) if traitable_class and field_name else None
        col = ibis_collection.ibis_col(field_name, trait)
        right = [ibis_collection.ibis_right_value(v) for v in self.serialize_right_value(field_name, traitable_class)]
        return ~col.isin(right)


# class REGEX(Op):


class BETWEEN(Op, label=''):
    def __new__(cls, a, b, bounds=(True, True)):
        obj = super().__new__(cls)
        assert isinstance(bounds, tuple) and len(bounds) == 2, f'{cls.__name__} - (bool, bool) is expected for bounds'

        bound_a, bound_b = bounds
        obj.left = GE(a) if bound_a else GT(a)
        obj.right = LE(b) if bound_b else LT(b)
        return obj

    def eval(self, x) -> bool:
        return self.left.eval(x) & self.right.eval(x)

    def ibis(self, ibis_collection, field_name: str = None, traitable_class: BTraitableClass = None):
        return (self.left.ibis(ibis_collection, field_name, traitable_class) &
                self.right.ibis(ibis_collection, field_name, traitable_class))

    def prefix_notation(self, field_name: str=None, traitable_class: BTraitableClass=None) -> dict:
        res = self.left.prefix_notation(field_name, traitable_class)
        res.update(self.right.prefix_notation(field_name, traitable_class))
        return res


class BoolOp(Op, ABC, label=''):
    s_false: IN = IN([])
    _op = None       # operator.and_ or operator.or_, set by subclasses
    _identity = None  # reduce identity: True for AND, False for OR

    @classmethod
    def _simplify(cls, expressions: tuple, false: IN) -> list: ...

    def __new__(cls, *expressions):
        expressions = cls._simplify(expressions, cls.s_false)
        if len(expressions) == 1:
            return expressions[0]

        obj = super().__new__(cls, expressions)
        return obj

    def prefix_notation(self, field_name: str=None, traitable_class: BTraitableClass=None) -> dict:
        rvalues = [pn for e in self.right_value if (pn := e.prefix_notation(field_name, traitable_class))]
        return {self.label: rvalues} if rvalues else {}

    def eval(self, ctx):
        return reduce(self._op, (e.eval(ctx) for e in self.right_value), self._identity)

    def ibis(self, ibis_collection, field_name: str = None, traitable_class: BTraitableClass = None):
        return reduce(self._op, (e.ibis(ibis_collection, field_name, traitable_class) for e in self.right_value), self._identity)


class AND(BoolOp):
    _op = operator.and_
    _identity = True

    @classmethod
    def _simplify(cls, expressions, false):
        return [false] if false in expressions else expressions


class OR(BoolOp):
    _op = operator.or_
    _identity = False

    @classmethod
    def _simplify(cls, expressions, false):
        expressions = [expression for expression in expressions if expression is not false]
        return [false] if not expressions else expressions


class f(_filter):
    def __init__(self, _f: f = None, _t: BTraitableClass = None, **named_expressions):
        self.filter = _f
        self.traitable_class = _t
        self.named_expressions = {
            name: expression if isinstance(expression, _filter) else EQ(expression) for name, expression in named_expressions.items()
        }

    def _apply(self, traitable_class, filter_fn, named_fn, reduce_fn, combine_fn):
        """Iterate self.filter and self.named_expressions, apply fns, combine with operator.and_."""
        tc = self.traitable_class or traitable_class
        f = filter_fn(self.filter, tc) if self.filter else None
        n = [(name, r) for name, op in self.named_expressions.items() if (r := named_fn(name, op, tc)) is not None]
        r = reduce_fn(n) if n else None
        return combine_fn(f,r) if f is not None and r is not None else f if f is not None else r

    def eval(self, traitable_instance: Traitable) -> bool:
        return self._apply(
            self.traitable_class,
            filter_fn = lambda filter_instance, traitable_class: filter_instance.eval(traitable_instance),
            named_fn = lambda trait_name, op, traitable_class: op.eval(traitable_instance[trait_name]),
            reduce_fn = lambda parts: reduce(operator.and_, map(operator.itemgetter(1),parts)) if parts else True,
            combine_fn=operator.and_
        )

    def prefix_notation(self, field_name: str=None, traitable_class: BTraitableClass=None) -> dict:
        return self._apply(
            traitable_class,
            filter_fn=lambda filt, tc: filt.prefix_notation(traitable_class=tc),
            named_fn=lambda name, op, tc: op.prefix_notation(field_name=name, traitable_class=tc),
            reduce_fn=lambda parts: dict(parts) if parts else None,
            combine_fn=lambda a,b: {AND.label: [a,b]}
        )

    def ibis(self, ibis_collection, field_name: str=None, traitable_class: BTraitableClass=None):
        return self._apply(
            traitable_class,
            filter_fn=lambda filt, tc: filt.ibis(ibis_collection, traitable_class=tc),
            named_fn=lambda name, op, tc: op.ibis(ibis_collection, name, tc),
            reduce_fn=lambda parts: reduce(operator.and_, map(operator.itemgetter(1),parts)) if parts else True,
            combine_fn=operator.and_
        )

