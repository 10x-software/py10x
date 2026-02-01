from core_10x.traitable import RT, M, Trait, Traitable


class A(Traitable):
    name: str = RT()


class B(A):
    name: int = M()


def name_ui_flags(cls):
    t: Trait = cls.trait('name')
    return t.ui_hint.flags


def test_uihint_modification():
    flags = (name_ui_flags(A), name_ui_flags(B))
    assert flags[0] == flags[1]
