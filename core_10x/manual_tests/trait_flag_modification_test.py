from core_10x_i import BFlags

from core_10x.traitable import M, T, Traitable


class X(Traitable):
    x: int = T(T.ID|T.RUNTIME)
    v: int = T(T.ID|T.RUNTIME)

class Y(X):
    v =  M(flags=(BFlags(0), T.ID))

if __name__ == '__main__':
    print(X(x=1,v=2).id().value)
    print(Y(x=1,v=2).id().value)