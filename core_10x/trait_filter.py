from core_10x.named_constant import NamedConstant

#===================================================================================================================================
#
#   age = LT(value)
#   name = 'Sasha'      #-- name = EQ('Sasha')
#   weight = BETWEEN(170, 180, bounds = (True, False)
#   weight =
#===================================================================================================================================

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

LABEL = _mongo_label

class _filter:
    def eval(self, left_value) -> bool:     raise NotImplementedError
    def prefix_notation(self) -> dict:      raise NotImplementedError

class Op(_filter):
    label = ''

    def __init_subclass__(cls, label: str = None):
        if label is None:
            label = getattr(LABEL, cls.__name__)
        cls.label = label

    def __init__(self, expression = None):
        self.right_value = expression

    def prefix_notation(self) -> dict:
        return { self.label: self.right_value }

class NOT_EMPTY(Op, label = ''):
    def prefix_notation(self) -> dict:        raise NotImplementedError
    def eval(self, left_value) -> bool:     return bool(left_value)

class EQ(Op):
    def eval(self, left_value) -> bool:     return left_value == self.right_value

class NE(Op):
    def eval(self, left_value) -> bool:     return left_value != self.right_value

class GT(Op):
    def eval(self, left_value) -> bool:     return left_value > self.right_value

class GE(Op):
    def eval(self, left_value) -> bool:     return left_value >= self.right_value

class LT(Op):
    def eval(self, left_value) -> bool:     return left_value < self.right_value

class LE(Op):
    def eval(self, left_value) -> bool:     return left_value <= self.right_value

class IN(Op):
    def __init__(self, values):
        assert isinstance(values, list) or isinstance(values, tuple), f'{self.__class__.__name__}() requires a list or tuple'
        super().__init__(values)

    def eval(self, left_value) -> bool:     return left_value in self.right_value

class NIN(IN):
    def eval(self, left_value) -> bool:     return not left_value in self.right_value

#class REGEX(Op):

class BETWEEN(Op, label = ''):
    def __init__(self, a, b, bounds = (True, True)):
        assert isinstance(bounds, tuple) and len(bounds) == 2, f'{self.__class__.__name__} - (bool, bool) is expected for bounds'

        bound_a, bound_b = bounds
        self.left   = GE(a) if bound_a else GT(a)
        self.right  = LE(b) if bound_b else LT(b)
        super().__init__()

    def eval(self, left_value) -> bool:
        return self.left.eval(left_value) and self.right.eval(left_value)

    def prefix_notation(self) -> dict:
        res = self.left.prefix_notation()
        res.update(self.right.prefix_notation())
        return res

class BoolOp(Op, label = ''):
    def __init__(self, *expressions):
        assert len(expressions) >= 2, f'{self.__class__.__name__} - at least two expressions are expected'
        super().__init__(expressions)

    def prefix_notation(self) -> dict:
        return {self.label: [ f.prefix_notation() for f in self.right_value ]}

class AND(BoolOp):
    def eval(self, left_value) -> bool:
        return all(f.eval(left_value) for f in self.right_value)

class OR(BoolOp):
    def eval(self, left_value) -> bool:
        return any(f.eval(left_value) for f in self.right_value)

class f(_filter):
    def __init__(self, _f: _filter = None, **named_expressions):
        self.filter = _f
        self.named_expressions = {
            name : expression if isinstance(expression, _filter) else EQ(expression)
            for name, expression in named_expressions.items()
        }

    def eval(self, traitable) -> bool:
        if self.filter:
            if not self.filter.eval(traitable):
                return False

        return all(item.eval(traitable.get_value(name)) for name, item in self.named_expressions.items())


    def prefix_notation(self) -> dict:
        clause = { name: item.prefix_notation() for name, item in self.named_expressions.items() }
        if self.filter and clause:
            clause = AND(self.filter.prefix_notation(), clause)

        return clause
