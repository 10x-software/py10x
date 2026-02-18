from core_10x.trait_definition import M
from core_10x.traitable import T, Traitable
from core_10x.xnone import XNone


class X(Traitable):
    x: int = T(T.ID | T.RUNTIME)
    v: int = T(T.ID | T.RUNTIME)

    def v_get(self):
        return self.x + 1


class Y(X):
    v: int = M(flags=(None, T.ID), default=3)


class Z(Y):
    v: float = M(default=XNone)

    def v_get(self):
        return self.x + 3


if __name__ == '__main__':
    x = X(x=1)
    y = Y(x=1)
    z = Z(x=1)
    print(x, x.v)
    print(y, y.v)
    print(z, z.v)




# NOTES:
# current classes trait.default override base classes trait_get
# current classes trait_get, overrides base classes trait.default, except if there is a trait modification  in this class, in which case, it needs to reset trait.default
# an error is thrown if trait_get and trait.default are defined in the same class (or there is a trait modification in the same class where trait_get is defined that does not reset trait.default from base class)