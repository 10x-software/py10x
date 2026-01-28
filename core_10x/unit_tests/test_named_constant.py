import pytest
from core_10x.named_constant import Enum, EnumBits, ErrorCode, NamedConstant, NamedConstantTable
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


def test_named_constant_value_and_table():
    class Row(NamedConstant):
        A = ()
        B = ()

    class Col(NamedConstant):
        X = ()
        Y = ()

    table = NamedConstantTable(
        Row,
        Col,
        A=(1, 2),
        B=(3, 4),
    )

    assert isinstance(table, NamedConstantTable)
    # Access by constant and by name
    assert table[Row.A]['X'] == 1
    assert table['A']['Y'] == 2
    assert table[Row.B]['X'] == 3
    assert table['B']['Y'] == 4

    # primary_key lookup by secondary key/value
    assert table.primary_key('Y', 2) == Row.A
    assert table.primary_key('Y', 4) == Row.B
    assert table.primary_key('Y', 999) is None


def test_enum_and_enum_bits_operations():
    class Priority(Enum, seed=1):
        LOW = ()
        MEDIUM = ()
        HIGH = ()

    assert int(Priority.LOW.value) == 1
    assert int(Priority.MEDIUM.value) == 2
    assert int(Priority.HIGH.value) == 3

    class Permissions(EnumBits):
        READ = ()
        WRITE = ()
        EXECUTE = ()

    read = Permissions.READ
    write = Permissions.WRITE
    both = read | write
    assert isinstance(both, Permissions)
    # bitwise ops may return equivalent-but-not-identical instances; compare by value/name
    assert (both & read).value == read.value
    assert (both & write).value == write.value
    assert Permissions.names_from_value(both.value) == ('READ', 'WRITE')

    # round trips from string/int/tuple via from_any_xstr
    assert Permissions.from_any_xstr(both.value).value == both.value
    assert Permissions.from_any_xstr(('READ', 'WRITE')).value == both.value
    none_const = Permissions.NONE
    assert Permissions.from_any_xstr(()).value == none_const.value


def test_error_code_formatting():
    class MyErrors(ErrorCode):
        NOT_FOUND = 'Item {0} not found'
        INVALID_VALUE = 'Invalid value {value}'

    assert MyErrors.NOT_FOUND(42) == 'Item 42 not found'
    assert MyErrors.INVALID_VALUE(value='X') == 'Invalid value X'
