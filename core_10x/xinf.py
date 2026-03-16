import math
import sys

class PInfType:
    def __hash__(self):                         return id(self)

    def __int__(self):                          return sys.maxsize
    def __bool__(self):                         return True
    def __float__(self):                        return math.inf
    def __repr__(self):                          return chr(8734)

    def __invert__(self):                       return MInf

    def __eq__(self, other):                    return other is self
    def __ne__(self, other):                    return not other is self
    def __lt__(self, other):                    return False
    def __le__(self, other):                    return other is self
    def __gt__(self, other):                    return not other is self
    def __ge__(self, other):                    return True

    def __abs__(self):                          return self
    def __neg__(self):                          return MInf
    def __add__(self, other):                   return self
    def __sub__(self, other):                   return self     #-- XInf - XInf is XInf (not NaN)
    def __mul__(self, other):                   return self
    def __pow__(self, power, modulo = None):    return self
    def __truediv__(self, other):               return self
    def __floordiv__(self, other):              return self

    def __init_subclass__(cls, **kwargs):
        raise TypeError('May not derive from Inf')

class MInfType:
    def __hash__(self):                         return id(self)

    def __int__(self):                          return ~sys.maxsize
    def __float__(self):                        return -math.inf
    def __repr__(self):                         return f'-{PInf.__repr__()}'

    def __invert__(self):                       return PInf

    def __eq__(self, other):                    return other is self
    def __ne__(self, other):                    return not other is self
    def __lt__(self, other):                    return not other is self
    def __le__(self, other):                    return True
    def __gt__(self, other):                    return False
    def __ge__(self, other):                    return other is self

    def __abs__(self):                          return PInf
    def __neg__(self):                          return PInf
    def __add__(self, other):                   return self
    def __sub__(self, other):                   return self
    def __mul__(self, other):                   return self
    def __pow__(self, power, modulo = None):    return self
    def __truediv__(self, other):               return self
    def __floordiv__(self, other):              return self

    def __init_subclass__(cls, **kwargs):
        raise TypeError('May not derive from Inf')

MInf = MInfType()
PInf = PInfType()
XInf = PInf

