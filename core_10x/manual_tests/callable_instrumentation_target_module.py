from core_10x.traitable import Traitable


class TargetBase(Traitable):
    def a_method(self):
        if True:
            return 1
        return 2


class TargetChild(TargetBase):
    def b_method(self):
        if True:
            return 1
        return 2
