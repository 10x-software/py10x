class XNoneType:
    """
    XNone is the 10x alternative to None representing a special empty object.
    As opposed to None, XNone may be used in many built-in python operations without extra checking, e.g.

    a_dict = XNone
    for key, value in a_dict.items():
        ...

    The above loop will merely exit on the first iteration.

    - all arithmetic operations with XNone will return XNone
    - all relational operations with XNone will return True or False accordingly
    - a call to XNone(*args, **kwargs) will return XNone
    """

    def __getattr__(self, item):              return self
    def __setattr__(self, key, value):        raise AttributeError('May not setattr to XNone')
    def __getitem__(self, item):              return self
    def __setitem__(self, key, value):        raise TypeError('\'XNone\' object does not support item assignment')
    def __call__(self, *args, **kwargs):      return self
    def __hash__(self):                       return id(self)

    def __int__(self):                        return self
    def __bool__(self):                       return False
    def __float__(self):                      return self

    def __repr__(self):                       return 'XNone'
    def __str__(self):                        return ''

    def __and__(self, other):                 return False
    def __or__(self, other):                  return other
    def __xor__(self, other):                 return other
    def __invert__(self):                     return None   #-- the opposite to XNone
    def __lshift__(self, other):              return self
    def __rshift__(self, other):              return self

    def __len__(self):                        return 0
    def __iter__(self):                       return self
    def __next__(self):                       raise StopIteration

    def keys(self):                           return self
    def values(self):                         return self
    def items(self):                          return self

    def __eq__(self, other):                  return other is self
    def __ne__(self, other):                  return other is not self
    def __lt__(self, other):                  return other is not self
    def __le__(self, other):                  return True
    def __gt__(self, other):                  return False
    def __ge__(self, other):                  return other is self
    def __abs__(self):                        return self
    def __neg__(self):                        return self
    def __add__(self, other):                 return self
    def __radd__(self, other):                return self
    def __sub__(self, other):                 return self
    def __rsub__(self, other):                return self
    def __mul__(self, other):                 return self
    def __rmul__(self, other):                return self
    def __pow__(self, power, modulo = None):  return self
    def __truediv__(self, other):             return self
    def __rtruediv__(self, other):            return self
    def __floordiv__(self, other):            return self
    def __rfloordiv__(self, other):           return self

    s_serialized = chr(8)

    def __init_subclass__(cls, **kwargs):
        raise TypeError('May not derive from XNone')

XNone = XNoneType()
