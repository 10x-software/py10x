from core_10x.exec_control import INTERACTIVE
from core_10x.traitable_heir import T, TraitableHeir


class HeirSample(TraitableHeir):
    key_a: str = T(T.ID)
    key_b: str = T(T.ID)
    value: int = T()


def test_serialize_object_passes_none_through():
    with INTERACTIVE():
        unshared = HeirSample()
        assert not unshared.id().value
        assert unshared.serialize_object() is None
