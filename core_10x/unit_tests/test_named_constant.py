from core_10x.named_constant import NamedConstant
from core_10x.traitable import T, Traitable


class Status(NamedConstant):
    ACTIVE = ()
    INACTIVE = ()


class X(Traitable):
    status: Status = T()


def test_serialize(ts_instance):
    with ts_instance:
        x = X(status=Status.ACTIVE)
        s = x.serialize_object()
        assert s == {'_id': x.id().value, '_rev': 0, 'status': 'ACTIVE'}

        x.save()

        assert x == X.load(x.id())
