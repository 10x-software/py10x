from __future__ import annotations

import operator
from abc import ABC, abstractmethod
from functools import reduce
from typing import TYPE_CHECKING

from core_10x.concrete_traits import any_trait, list_trait
from core_10x.xnone import XNone

if TYPE_CHECKING:
    from core_10x.trait import Trait
    from core_10x.traitable import Traitable

#=======================================================================================================================
#
#   age = LT(value)
#   name = 'Sasha'      #-- name = EQ('Sasha')
#   weight = BETWEEN(170, 180, bounds = (True, False)
#
#=======================================================================================================================

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
    NOT     = '$not'
    NOR     = '$nor'

LABEL = _mongo_label


class _filter(ABC):
    s_field_op = False

    @abstractmethod
    def negate(self) -> _filter | None: ...

    @abstractmethod
    def eval(self, left_value) -> bool: ...

    @abstractmethod
    def prefix_notation(self, field_name: str = None, trait_dir: dict[str, Trait] | None = None) -> dict: ...

    @abstractmethod
    def ibis(self, ibis_collection, field_name: str = None, trait_dir: dict[str, Trait] | None = None): ...


_ARRAY_TRAITS = (list_trait, any_trait)
_NOT_ARRAY = {LABEL.NOT: {'$type': 'array'}}

def _trait_of(field_name: str | None, trait_dir: dict[str, Trait] | None) -> Trait | None:
    return trait_dir.get(field_name) if trait_dir and field_name else None

def _is_collection(value) -> bool:
    return isinstance(value, (list, tuple, set))

def _is_list_item(trait: Trait | None, value) -> bool:
    return isinstance(trait, list_trait) and not _is_collection(value) and value is not XNone

def _serialize_filter_value(trait: Trait, value):
    #-- A scalar against a list/set trait means "contains": serialize it as a list element;
    #-- Mongo, for example, matches $eq/$in against array elements. The stored form is [class_id, *items].
    #-- Known gap: heterogeneous lists store non-primitive items typed (e.g. a date as {_type, _cls, _obj}), so those won't match.
    if _is_list_item(trait, value):
        return trait.serialize_value([value])[1]

    return trait.serialize_value(value, replace_xnone = True)

def _whole_value_match(left: list | set, right) -> bool:
    #-- type(left)(right) makes a tuple filter value equal to a stored list, as it is in Mongo.
    return _is_collection(right) and type(left)(right) == left

def _list_trait_match(left: list | set, right) -> bool:
    #-- In-memory twin of the above: a scalar matches an item, a collection matches the whole list/set.
    return _whole_value_match(left, right) if _is_collection(right) else right in left

def _ibis_via_in(trait: Trait | None, value) -> bool:
    #-- IN handles what a single SQL comparison can't: list items, and a number against an any-typed field.
    return _is_list_item(trait, value) or (isinstance(value, (int, float)) and isinstance(trait, any_trait))

def _mongo_items_expr(field_name: str, values, serialized: list, exposed: list) -> dict:
    #-- Skips the class id. XNone serializes to None too, but means "unset" rather than a None item.
    path = f'${field_name}'
    items = {'$cond': [{'$isArray': path}, {'$slice': [path, 1, 2**31 - 1]}, []]}
    unset = {'$eq': [{'$ifNull': [path, None]}, None]}
    return {LABEL.OR: [
        unset if v is XNone else {'$in': [{'$literal': serial}, items]}
        for v, serial in zip(values, serialized, strict = True) if serial in exposed
    ]}

def _mongo_match(field_name: str, trait_dir: dict[str, Trait] | None, values) -> dict | None:
    """The query for ``values`` if plain Mongo array matching would give the wrong answer for this trait; else None.

    Mongo tests every array element. An any-typed trait has no item matching, and in a list's ``[class_id, *items]``
    the class id is a str, or None for a heterogeneous list. The field condition stays next to ``$expr``, which cannot use an index.
    """
    trait = _trait_of(field_name, trait_dir)
    if not isinstance(trait, _ARRAY_TRAITS):
        return None
    serialized = [_serialize_filter_value(trait, v) for v in values]
    is_any = isinstance(trait, any_trait)
    exposed = [v for v in serialized if (not isinstance(v, (list, tuple)) if is_any else v is None or isinstance(v, str))]
    if not exposed:
        return None
    match = {field_name: {LABEL.IN: exposed, **_NOT_ARRAY}} if is_any else (
        {field_name: {LABEL.IN: exposed}, '$expr': _mongo_items_expr(field_name, values, serialized, exposed)}
    )
    others = [v for v in serialized if v not in exposed]
    return {LABEL.OR: [{field_name: {LABEL.IN: others}}, match]} if others else match

class Op(_filter, ABC):
    label = ''
    s_field_op = True

    def negate(self):
        return None

    def __init_subclass__(cls, label: str = None):
        if label is None:
            label = getattr(LABEL, cls.__name__)
        cls.label = label

    def __new__(cls, expression = None):
        obj = super().__new__(cls)
        obj.right_value = expression
        return obj

    def serialize_right_value(self, field_name: str, trait_dir: dict[str, Trait] | None):
        return _serialize_filter_value(trait, self.right_value) if (trait := _trait_of(field_name, trait_dir)) else self.right_value

    def prefix_notation(self, field_name: str = None, trait_dir: dict[str, Trait] | None = None, mongo_doc: bool = False) -> dict:
        """With ``mongo_doc``, a whole query document for the field, which may need more than the field's own key."""
        # noinspection PyTypeChecker
        condition = {self.label: self.serialize_right_value(field_name, trait_dir)}
        return {field_name: condition} if mongo_doc else condition

    @staticmethod
    def _eval(left, right) -> bool:
        raise NotImplementedError

    def eval(self, left_value, field_name: str = None, trait_dir: dict[str, Trait] | None = None) -> bool:
        return self._eval(left_value, self.right_value)

    def ibis(self, ibis_collection, field_name: str = None, trait_dir: dict[str, Trait] | None = None):
        trait = _trait_of(field_name, trait_dir)
        col, (right,) = ibis_collection.ibis_compare_pair(field_name, trait, [self.serialize_right_value(field_name, trait_dir)])
        return self._eval(col, right)

class NOT_EMPTY(Op, label = ''):
    def prefix_notation(self, field_name: str = None, trait_dir: dict[str, Trait] | None = None, mongo_doc: bool = False) -> dict:
        raise NotImplementedError

    @staticmethod
    def _eval(left, right) -> bool:
        return bool(left)

    def ibis(self, ibis_collection, field_name: str = None, trait_dir: dict[str, Trait] | None = None):
        raise NotImplementedError

class _ValueOp(Op, label = ''):
    """Tests for one of the _values(), or for none of them if negated."""
    s_negated = False

    def _values(self):
        return [self.right_value]

    def eval(self, left_value, field_name: str = None, trait_dir: dict[str, Trait] | None = None) -> bool:
        if not isinstance(left_value, (list, set)):
            return super().eval(left_value)
        match = _list_trait_match if isinstance(_trait_of(field_name, trait_dir), list_trait) else _whole_value_match
        return any(match(left_value, v) for v in self._values()) != self.s_negated

    def prefix_notation(self, field_name: str = None, trait_dir: dict[str, Trait] | None = None, mongo_doc: bool = False) -> dict:
        match = _mongo_match(field_name, trait_dir, self._values()) if mongo_doc else None
        if not match:
            return super().prefix_notation(field_name, trait_dir, mongo_doc)
        return {LABEL.NOR: [match]} if self.s_negated else match

class EQ(_ValueOp):
    @staticmethod
    def _eval(left, right) -> bool:
        return left == right

    def ibis(self, ibis_collection, field_name: str = None, trait_dir: dict[str, Trait] | None = None):
        use_in = _ibis_via_in(_trait_of(field_name, trait_dir), self.right_value)
        return IN([self.right_value]).ibis(ibis_collection, field_name, trait_dir) if use_in else super().ibis(ibis_collection, field_name, trait_dir)

class NE(_ValueOp):
    s_negated = True

    @staticmethod
    def _eval(left, right) -> bool:
        return left != right

    def ibis(self, ibis_collection, field_name: str = None, trait_dir: dict[str, Trait] | None = None):
        # A missing blob key unwraps to SQL NULL, and `NULL != x` is NULL (row excluded) under
        # three-valued logic. Mongo's $ne matches missing fields, so match that here too — but
        # not when the right-hand side is itself None/XNone: NE(XNone) means "field IS NOT
        # NULL" (col != None already compiles to that), and ORing isnull() there would make it
        # tautologically true instead.
        trait = _trait_of(field_name, trait_dir)
        if _ibis_via_in(trait, self.right_value):
            return NIN([self.right_value]).ibis(ibis_collection, field_name, trait_dir)
        serialized = self.serialize_right_value(field_name, trait_dir)
        col, (right,) = ibis_collection.ibis_compare_pair(field_name, trait, [serialized])
        cmp = col != right
        return cmp if serialized is None else col.isnull() | cmp

class _Ordered(Op, label = ''):
    """A comparison with a scalar never looks inside an array, whatever the trait: stored arrays just don't match."""

    def _may_see_array(self, field_name: str, trait_dir: dict[str, Trait] | None) -> bool:
        return not _is_collection(self.right_value) and isinstance(_trait_of(field_name, trait_dir), _ARRAY_TRAITS)

    def eval(self, left_value, field_name: str = None, trait_dir: dict[str, Trait] | None = None) -> bool:
        if isinstance(left_value, (list, set)) and not _is_collection(self.right_value):
            return False
        return super().eval(left_value)

    def prefix_notation(self, field_name: str = None, trait_dir: dict[str, Trait] | None = None, mongo_doc: bool = False) -> dict:
        condition = super().prefix_notation(field_name, trait_dir)
        if self._may_see_array(field_name, trait_dir):
            condition |= _NOT_ARRAY
        return {field_name: condition} if mongo_doc else condition

    def ibis(self, ibis_collection, field_name: str = None, trait_dir: dict[str, Trait] | None = None):
        if self._may_see_array(field_name, trait_dir):
            serialized = self.serialize_right_value(field_name, trait_dir)
            if (col := ibis_collection.ibis_json_scalar(field_name, serialized)) is not None:
                return self._eval(col, serialized)
        return super().ibis(ibis_collection, field_name, trait_dir)

class GT(_Ordered):
    @staticmethod
    def _eval(left, right) -> bool:
        return left > right

class GE(_Ordered):
    @staticmethod
    def _eval(left, right) -> bool:
        return left >= right

class LT(_Ordered):
    @staticmethod
    def _eval(left, right) -> bool:
        return left < right

class LE(_Ordered):
    @staticmethod
    def _eval(left, right) -> bool:
        return left <= right

class IN(_ValueOp):
    def __new__(cls, values: list | tuple | set):
        assert _is_collection(values), f'{cls.__name__}() requires a list, tuple, or set'
        return super().__new__(cls, values)

    def _values(self):
        return self.right_value

    def serialize_right_value(self, field_name: str, trait_dir: dict[str, Trait] | None):
        return (
            [_serialize_filter_value(trait, value) for value in self.right_value]
            if (trait := _trait_of(field_name, trait_dir))
            else self.right_value
        )

    @staticmethod
    def _eval(left, right) -> bool:
        return left in right

    def _ibis_isin(self, ibis_collection, field_name: str, trait_dir: dict[str, Trait] | None) -> tuple:
        """``(col, isin_pred_or_None, has_none)`` with ``None`` kept out of the SQL ``IN`` list.

        Under three-valued logic ``x IN (a, NULL)`` is never TRUE and ``x NOT IN (a, NULL)`` is
        never TRUE either, so a ``None`` in the list would silently poison the whole predicate.
        It is stripped here and folded back by the caller as an explicit NULL test — which is
        also exactly what Mongo means by ``$in`` / ``$nin`` matching missing fields.

        ``isin_pred`` is None when every value was ``None``. Callers handle an empty list first.
        """
        trait = _trait_of(field_name, trait_dir)
        items, values = [], []
        for value, serialized in zip(self.right_value, self.serialize_right_value(field_name, trait_dir), strict = True):
            (items if _is_list_item(trait, value) else values).append(serialized)
        concrete = [v for v in values if v is not None]
        col, right = ibis_collection.ibis_compare_pair(field_name, trait, concrete)
        pred = col.isin(right) if concrete else None
        if items:
            contains = ibis_collection.ibis_list_contains(field_name, items)
            pred = contains if pred is None else pred | contains
        return col, pred, len(concrete) != len(values)

    def ibis(self, ibis_collection, field_name: str = None, trait_dir: dict[str, Trait] | None = None):
        if not self.right_value:
            return False  # nothing to bind; an empty IN matches no value
        col, pred, has_none = self._ibis_isin(ibis_collection, field_name, trait_dir)
        if pred is None:
            return col.isnull()  # IN([None, ...]): only missing / null qualifies
        return col.isnull() | pred if has_none else pred

class NIN(IN):
    s_negated = True

    @staticmethod
    def _eval(left, right) -> bool:
        return left not in right

    def ibis(self, ibis_collection, field_name: str = None, trait_dir: dict[str, Trait] | None = None):
        # Mongo's $nin matches missing fields (same reasoning as NE.ibis) — *unless* None is
        # itself excluded, in which case missing/null are excluded along with it.
        if not self.right_value:
            return True
        col, pred, has_none = self._ibis_isin(ibis_collection, field_name, trait_dir)
        if pred is None:
            return col.notnull()  # NIN([None, ...]): every field that is present
        return col.notnull() & ~pred if has_none else col.isnull() | ~pred

# class REGEX(Op):

class BETWEEN(Op, label = ''):
    def __new__(cls, a, b, bounds = (True, True)):
        obj = super().__new__(cls)
        assert isinstance(bounds, tuple) and len(bounds) == 2, f'{cls.__name__} - (bool, bool) is expected for bounds'

        bound_a, bound_b = bounds
        obj.left = GE(a) if bound_a else GT(a)
        obj.right = LE(b) if bound_b else LT(b)
        return obj

    def eval(self, x, field_name: str = None, trait_dir: dict[str, Trait] | None = None) -> bool:
        return self.left.eval(x, field_name, trait_dir) & self.right.eval(x, field_name, trait_dir)

    def ibis(self, ibis_collection, field_name: str = None, trait_dir: dict[str, Trait] | None = None):
        return self.left.ibis(ibis_collection, field_name, trait_dir) & self.right.ibis(ibis_collection, field_name, trait_dir)

    def prefix_notation(self, field_name: str = None, trait_dir: dict[str, Trait] | None = None, mongo_doc: bool = False) -> dict:
        res = self.left.prefix_notation(field_name, trait_dir)
        res.update(self.right.prefix_notation(field_name, trait_dir))
        return {field_name: res} if mongo_doc else res

class FALSE(_filter):
    """The match-nothing query. Combinators absorb only ``BoolOp.s_false``; ``OR()`` is that instance."""

    def eval(self, left_value) -> bool:
        return False

    def prefix_notation(self, field_name: str = None, trait_dir: dict[str, Trait] | None = None) -> dict:
        return {'$expr': False}

    def ibis(self, ibis_collection, field_name: str = None, trait_dir: dict[str, Trait] | None = None):
        return False

    def negate(self) -> _filter:
        return AND()  # match-all


class BoolOp(Op, ABC, label=''):
    s_field_op = False
    s_false: FALSE = FALSE()
    _op = None  # operator.and_ or operator.or_, set by subclasses
    _identity = None  # reduce identity: True for AND, False for OR

    @abstractmethod
    def negate(self) -> _filter: ...

    @classmethod
    def _simplify(cls, expressions: tuple, false: FALSE) -> list: ...

    def __new__(cls, *expressions):
        expressions = cls._simplify(expressions, cls.s_false)
        if len(expressions) == 1:
            return expressions[0]

        obj = super().__new__(cls, expressions)
        return obj

    def prefix_notation(self, field_name: str = None, trait_dir: dict[str, Trait] | None = None) -> dict:
        ident = self._identity
        rvalues = [pn for e in self.right_value if (pn := e.prefix_notation(field_name, trait_dir)) or not ident]
        return {self.label: rvalues} if rvalues and all(rvalues) else {}

    def eval(self, ctx):
        return reduce(self._op, (e.eval(ctx) for e in self.right_value), self._identity)

    def ibis(self, ibis_collection, field_name: str = None, trait_dir: dict[str, Trait] | None = None):
        return reduce(self._op, (e.ibis(ibis_collection, field_name, trait_dir) for e in self.right_value), self._identity)

class AND(BoolOp):
    _op = operator.and_
    _identity = True

    @classmethod
    def _simplify(cls, expressions, false):
        return [false] if false in expressions else expressions

    def negate(self) -> _filter:
        return OR(*(NOT(child) for child in self.right_value))

class OR(BoolOp):
    _op = operator.or_
    _identity = False

    @classmethod
    def _simplify(cls, expressions, false):
        expressions = [expression for expression in expressions if expression is not false]
        return [false] if not expressions else expressions

    def negate(self) -> _filter:
        return AND(*(NOT(child) for child in self.right_value))

class f(_filter):
    def __init__(self, _f: f = None, trait_dir: dict[str, Trait] | None = None, **named_expressions):
        self.filter = _f
        self.trait_dir = trait_dir
        self.named_expressions = {
            name: expression if isinstance(expression, _filter) else EQ(expression) for name, expression in named_expressions.items()
        }
        # Mongo has no field-level $and/$or. Combine filters, e.g. OR(f(x=1), f(x=2)), or use x=IN([...]).
        assert not (bad := [name for name, op in self.named_expressions.items() if not op.s_field_op]), f'{bad}: AND/OR/f() are not field operators'

    def _apply(self, trait_dir, filter_fn, named_fn, reduce_fn, combine_fn, *, empty):
        """Iterate self.filter and self.named_expressions, apply fns, combine with operator.and_.

        ``empty`` is the no-constraint result when both sides are absent (``f()``): True for
        eval/ibis, ``{}`` for prefix_notation.
        """
        td = self.trait_dir or trait_dir
        f = filter_fn(self.filter, td) if self.filter else None
        n = [(name, r) for name, op in self.named_expressions.items() if (r := named_fn(name, op, td)) is not None]
        r = reduce_fn(n) if n else None
        if f is not None and r is not None:
            return combine_fn(f, r)
        if f is not None:
            return f
        if r is not None:
            return r
        return empty

    def eval(self, traitable_instance: Traitable) -> bool:
        return self._apply(
            type(traitable_instance).s_dir,
            filter_fn   = lambda filter_instance, td: filter_instance.eval(traitable_instance),
            named_fn    = lambda trait_name, op, td: op.eval(traitable_instance[trait_name], trait_name, td),
            reduce_fn   = lambda parts: reduce(operator.and_, map(operator.itemgetter(1), parts)) if parts else True,
            combine_fn  = operator.and_,
            empty       = True,
        )

    def prefix_notation(self, field_name: str = None, trait_dir: dict[str, Trait] | None = None) -> dict:
        return self._apply(
            trait_dir,
            filter_fn   = lambda filt, td: filt.prefix_notation(trait_dir=td),
            named_fn    = lambda name, op, td: op.prefix_notation(name, td, mongo_doc = True),
            reduce_fn   = lambda parts: parts[0][1] if len(parts) == 1 else {AND.label: [document for _, document in parts]},
            combine_fn  = lambda a, b: {AND.label: [a, b]},
            empty       = {},
        )

    def ibis(self, ibis_collection, field_name: str = None, trait_dir: dict[str, Trait] | None = None):
        return self._apply(
            trait_dir,
            filter_fn=lambda filt, td: filt.ibis(ibis_collection, trait_dir=td),
            named_fn=lambda name, op, td: op.ibis(ibis_collection, name, td),
            reduce_fn=lambda parts: reduce(operator.and_, map(operator.itemgetter(1), parts)) if parts else True,
            combine_fn=operator.and_,
            empty=True,
        )

    def negate(self) -> _filter:
        """An ``f`` is the conjunction of its fields, so its negation is an OR."""
        parts = [f(**{name: NOT(op)}, trait_dir=self.trait_dir) for name, op in self.named_expressions.items()]
        if self.filter is not None:
            parts.append(f(NOT(self.filter), trait_dir=self.trait_dir))
        return OR(*parts) if parts else BoolOp.s_false

class NOT(Op):
    """``f(age=NOT(GT(5)))`` is a ``$nor`` on the field. ``NOT(f(...))`` rewrites via De Morgan."""

    def __new__(cls, expression: _filter):
        negated = expression.negate()
        return super().__new__(cls, expression) if negated is None else negated

    def negate(self) -> _filter:
        return self.right_value

    def prefix_notation(self, field_name: str = None, trait_dir: dict[str, Trait] | None = None, mongo_doc: bool = False) -> dict:
        rv_notation = self.right_value.prefix_notation(field_name, trait_dir, mongo_doc = mongo_doc)
        return {LABEL.NOR: [rv_notation]} if mongo_doc else {self.label: rv_notation}

    def eval(self, left_value, field_name: str = None, trait_dir: dict[str, Trait] | None = None) -> bool:
        return not self.right_value.eval(left_value, field_name, trait_dir)

    def ibis(self, ibis_collection, field_name: str = None, trait_dir: dict[str, Trait] | None = None):
        # ``NOT (col > 5)`` is NULL when col is NULL, so the row would disappear. Mongo ``$not``
        # matches a missing field. Keep the row when the inner predicate is not strictly true.
        pred = self.right_value.ibis(ibis_collection, field_name, trait_dir)
        if isinstance(pred, bool):
            return not pred
        return pred.isnull() | ~pred
