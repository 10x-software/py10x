from math import exp, log
from core_10x.named_constant import NamedConstant, Nucleus, NamedConstantValue, NamedConstantTable, Enum, ErrorCode

class COLOR(NamedConstant, lowercase_values = True):
    RED         = ()
    BLUE        = ()
    GREEN       = ()
    LIGHTGREEN  = ()

class XCOLOR(COLOR):
    BLACK       = ()
    WHITE       = ()

class WEIGHT(NamedConstant):
    LB  = ()
    KG  = ()
    CT  = ()

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


# TODO: it fails now - fix!
COLOR_WEIGHT = NamedConstantValue(
    COLOR,
    RED         = 10,
    BLUE        = 20,
    GREEN       = 30,
    LIGHTGREEN  = 35
)

COLOR_CODE = NamedConstantValue(
    COLOR,
    RED         = 1.0,
    BLUE        = 11.1,
    GREEN       = 12.2,
    LIGHTGREEN  = 13.3
)

COMPOUNDING_TRANSFORM_TABLE = NamedConstantTable(COMPOUNDING, COMPOUND_TRANSFORM,
   #               RATE_TO_ACCRUAL                             ACCRUAL_TO_RATE
   SIMPLE      = ( lambda t, r:  1. + r * t,                   lambda t, a: (a - 1.) / t                       if t else 0. ),
   ANNUAL      = ( lambda t, r: (1. + r      ) **  t,          lambda t, a:  a ** (1. / t)       - 1.          if t else 0. ),
   SEMI_ANNUAL = ( lambda t, r: (1. + r /  2.) ** (t *  2.),   lambda t, a: (a ** (1. / t /  2.) - 1.) * 2.    if t else 0. ),
   QUARTERLY   = ( lambda t, r: (1. + r /  4.) ** (t *  4.),   lambda t, a: (a ** (1. / t /  4.) - 1.) * 4.    if t else 0. ),
   MONTHLY     = ( lambda t, r: (1. + r / 12.) ** (t * 12.),   lambda t, a: (a ** (1. / t / 12.) - 1.) * 12.   if t else 0. ),
   WEEKLY      = ( lambda t, r: (1. + r / 52.) ** (t * 52.),   lambda t, a: (a ** (1. / t / 52.) - 1.) * 52.   if t else 0. ),
   CONTINUOUS  = ( lambda t, r: exp(r * t),                    lambda t, a: log(a) / t ),
)

class EVEN_NUMBER(Enum, step = 2):
    ZERO    = ()
    TWO     = ()
    FOUR    = ()

class A_PROBLEM(ErrorCode):
    DOES_NOT_EXIST  = 'Entity {cls}.{id} does not exist'
    REV_CONFLICT    = 'Entity {cls}.{id} - revision {rev} is outdated'
    SAVE_FAILED     = 'Failed to save entity {cls}.{id}'

if __name__ == '__main__':
    print( COLOR.LIGHTGREEN.value)
    sgreen = Nucleus.serialize_any(COLOR.GREEN, False)
    swhite = Nucleus.serialize_any(XCOLOR.WHITE, False)

    assert Nucleus.deserialize_any(swhite) is XCOLOR.WHITE

    ####print(COLOR_WEIGHT.GREEN, COLOR_CODE.GREEN)

    print(A_PROBLEM.REV_CONFLICT(cls = 'XXX', id = '145678', rev = '3'))
