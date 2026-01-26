import pytest
from core_10x.named_constant import NamedConstant
from core_10x.traitable import T, Traitable


class Status(NamedConstant):
    ACTIVE = ()
    INACTIVE = ()


class StatusEx(Status):
    DEPRECATED = ()


class X(Traitable):
    status: Status = T()


@pytest.mark.parametrize('status', [Status.ACTIVE, StatusEx.DEPRECATED])
def test_serialize(ts_instance, status):
    with ts_instance:
        x = X(status=status)
        s = x.serialize_object()
        status_val = {'_type': '_nx', '_cls': 'test_named_constant/StatusEx', '_obj': 'DEPRECATED'} if status is StatusEx.DEPRECATED else 'ACTIVE'
        assert s == {'_id': x.id().value, '_rev': 0, 'status': status_val}

        x.save()

        assert x == X.load(x.id())
