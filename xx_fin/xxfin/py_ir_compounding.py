import math

from core_10x.named_constant import NamedConstant, NamedConstantTable


class COMPOUNDING(NamedConstant):
    SIMPLE      = ()
    ANNUAL      = ()
    SEMI_ANNUAL = ()
    QUARTERLY   = ()
    MONTHLY     = ()
    WEEKLY      = ()
    CONTINUOUS  = ()

class COMPOUND_TRANSFORM(NamedConstant):
    RATE_TO_ACCRUAL = ()
    ACCRUAL_TO_RATE = ()

_TABLE = NamedConstantTable(COMPOUNDING, COMPOUND_TRANSFORM,
    #               RATE_TO_ACCRUAL                             ACCRUAL_TO_RATE
    SIMPLE      = ( lambda t, r:  1. + r * t,                   lambda t, a: (a - 1.) / t                       if t else 0. ),
    ANNUAL      = ( lambda t, r: (1. + r      ) **  t,          lambda t, a:  a ** (1. / t)       - 1.          if t else 0. ),
    SEMI_ANNUAL = ( lambda t, r: (1. + r /  2.) ** (t *  2.),   lambda t, a: (a ** (1. / t /  2.) - 1.) * 2.    if t else 0. ),
    QUARTERLY   = ( lambda t, r: (1. + r /  4.) ** (t *  4.),   lambda t, a: (a ** (1. / t /  4.) - 1.) * 4.    if t else 0. ),
    MONTHLY     = ( lambda t, r: (1. + r / 12.) ** (t * 12.),   lambda t, a: (a ** (1. / t / 12.) - 1.) * 12.   if t else 0. ),
    WEEKLY      = ( lambda t, r: (1. + r / 52.) ** (t * 52.),   lambda t, a: (a ** (1. / t / 52.) - 1.) * 52.   if t else 0. ),
    CONTINUOUS  = ( lambda t, r: math.exp(r * t),               lambda t, a: math.log(a) / t                    if t else 0. ),
)

def compounding_apply(comp: COMPOUNDING, transform: COMPOUND_TRANSFORM, t: float, v: float) -> float:
    return _TABLE[comp][transform](t, v)
