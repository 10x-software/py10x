from __future__ import annotations

from math import exp, log

from core_10x.named_constant import (
    Enum,
    EnumBits,
    ErrorCode,
    NamedConstant,
    NamedConstantTable,
    NamedConstantValue,
    Nucleus,
)


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

class ICON(EnumBits):
    FILE = ('material/file',)
    STOP = ('material/stop',)

class TEXT_ALIGN(NamedConstant):
    s_vertical = 0xf << 4

    LEFT = 1
    CENTER = 6
    RIGHT = 11
    TOP = LEFT << 4
    V_CENTER = CENTER << 4
    BOTTOM = RIGHT << 4

    @classmethod
    def from_str(cls, s: str) -> TEXT_ALIGN:
        return super().from_str(s.upper()) # type: ignore[return-value]

    def rio_attr(self) -> str:
        return 'align_y' if self.value & self.s_vertical else 'align_x'

    def rio_value(self) -> float:
        return ((self.value >> 4 if self.value & self.s_vertical else self.value)-1) /10

if __name__ == '__main__':
    from core_10x.manual_tests.named_constant_test import COLOR, XCOLOR

    print( COLOR.LIGHTGREEN.value)
    sgreen = Nucleus.serialize_any(COLOR.GREEN, False)
    swhite = Nucleus.serialize_any(XCOLOR.WHITE, False)
    print(sgreen)
    print(swhite)

    assert Nucleus.deserialize_dict(swhite) is XCOLOR.WHITE
    #print(COLOR_WEIGHT.GREEN, COLOR_CODE.GREEN) #TODO: FIX!

    print(A_PROBLEM.REV_CONFLICT(cls = 'XXX', id = '145678', rev = '3'))

    x,y = TEXT_ALIGN.from_str('left'), TEXT_ALIGN.from_str('v_center')
    print( x, y, x.rio_attr(), y.rio_attr(), x.value, y.value, x.rio_value(), y.rio_value() )