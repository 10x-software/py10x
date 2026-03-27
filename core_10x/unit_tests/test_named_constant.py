import pytest
from core_10x.named_constant import Enum, EnumBits, ErrorCode, NamedCallable, NamedConstant, NamedConstantTable, NamedConstantValue
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


def test_named_constant_item_lookup():
    class Color(NamedConstant):
        RED   = ()
        GREEN = ()
        BLUE  = ()

    assert Color.item('RED')   is Color.RED
    assert Color.item('GREEN') is Color.GREEN
    assert Color.item('BLUE')  is Color.BLUE
    assert Color.item('PURPLE') is None


def test_named_constant_value_standalone():
    class Metric(NamedConstant):
        RISK   = ()
        RETURN = ()

    row = NamedConstantValue(Metric, RISK=0.1, RETURN=0.9)

    # Access by constant instance
    assert row[Metric.RISK]   == 0.1
    assert row[Metric.RETURN] == 0.9
    # Access by string name
    assert row['RISK']   == 0.1
    assert row['RETURN'] == 0.9
    # Attribute-style access
    assert row.RISK   == 0.1
    assert row.RETURN == 0.9
    # Mutation is not allowed
    with pytest.raises(AssertionError):
        row['RISK'] = 99.0


def test_named_constant_table_extend():
    class BaseAsset(NamedConstant):
        CASH   = ()
        EQUITY = ()

    class Attr(NamedConstant):
        RISK_WEIGHT = ()

    base = NamedConstantTable(BaseAsset, Attr, CASH=(0.0,), EQUITY=(1.0,))

    class ExtAsset(BaseAsset):
        COMMODITY = ()

    ext = base.extend(ExtAsset, COMMODITY=(0.8,))

    # Original rows are preserved
    assert ext[ExtAsset.CASH][Attr.RISK_WEIGHT]      == 0.0
    assert ext[ExtAsset.EQUITY][Attr.RISK_WEIGHT]    == 1.0
    # New row is accessible
    assert ext[ExtAsset.COMMODITY][Attr.RISK_WEIGHT] == 0.8
    # Original table is unchanged
    assert base.data.get(ExtAsset.COMMODITY) is None


def test_named_callable_members_and_call():
    class Agg(NamedCallable):
        SUM  = lambda items: sum(items)
        MEAN = lambda items: sum(items) / len(items)

    # Members are NamedConstant instances with callable values
    assert Agg.SUM.name  == 'SUM'
    assert Agg.MEAN.name == 'MEAN'

    # Callable via the constant directly
    assert Agg.SUM([1, 2, 3])  == 6
    assert Agg.MEAN([2, 4, 6]) == 4.0

    # item() lookup works for NamedCallable too
    assert Agg.item('SUM') is Agg.SUM
    assert Agg.item('MISSING') is None


def test_named_callable_just_func():
    double = NamedCallable.just_func(lambda x: x * 2)

    assert double(5)  == 10
    assert double(0)  == 0
    assert double(-3) == -6
