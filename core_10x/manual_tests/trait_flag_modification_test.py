from core_10x_i import BFlags

from core_10x.trait_definition import M
from core_10x.traitable import T, Traitable


class X(Traitable):
    x: int = T(T.ID|T.RUNTIME)
    v: int = T(T.ID|T.RUNTIME)
    def v_get(self):
        return self.x+1

class Y(X):
    v: int =  M(flags=(BFlags(0), T.ID),get=lambda self:2)

class Z(Y):
    v: float = M(get=None)
    def v_get(self):
        return self.x+3

if __name__ == '__main__':
    x = X(x=1)
    y = Y(x=1)
    z = Z(x=1)
    print(x,x.v)
    print(y,y.v)
    print(z,z.v)

    print(getattr(x,'__dict__','n/a'))
    print(getattr(y,'__dict__','n/a'))
    print(getattr(z,'__dict__','n/a'))


#NOTES:
# current classes trait.get override base classes trait_get
# current classes trait_get, overrides base classes trait.get, except if there is a trait modification  in this class, in which case, it needs to reset trait.get
# en error is thrown if trait_get and trait.get are defined in the same class (or there is a trait modification that does nto reset trait.get)
# TODO: should trait.default should work just as trait.get?