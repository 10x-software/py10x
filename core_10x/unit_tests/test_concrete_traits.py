import pytest

from core_10x.trait_method_error import TraitMethodError
from core_10x.code_samples.person import Person
from core_10x.exec_control import GRAPH_OFF
from core_10x.trait_definition import T
from core_10x.traitable import Traitable


def _test( data_type, values, expected_values):
    class TestableTraitable(Traitable):
        xid: int = T(T.ID, default=1)
        value: data_type = T(1)
    p = TestableTraitable(xid=1)
    for v, ev in zip(values, expected_values):
        if isinstance(ev, type) and issubclass(ev, Exception):
            with pytest.raises(ev):
                p.value = v
        else:
            p.value = v
            assert p.value == ev
            assert {'_id': '1', '_rev': 0, 'xid': 1, 'value': ev} == p.serialize(True)
   # q = TestableTraitable()
   # assert q.deserialize(p.serialize(True)) is p


def test_int_trait():
    data_type = int
    values = [180, 180.1, '180', 'abc', None, '']
    _test(data_type, values, values)

    with GRAPH_OFF(convert_values=True):
        #TODO: unify exception types thrown on conversion errors
        _test(data_type, values, [180, 180, 180, TypeError, TraitMethodError, TypeError])

    with GRAPH_OFF(debug=True):
        _test(data_type, values, [180, TypeError,TypeError,TypeError,TypeError, TypeError])


def test_bool_trait():
    data_type = bool
    values = [True, False, 1, 0, 'yes', 'no', 'abc', None, '']
    _test(data_type, values, values)

    with GRAPH_OFF(convert_values=True):
        _test(data_type, values, [True, False, True, False, TypeError, TypeError,TypeError,False,TypeError])

    with GRAPH_OFF(debug=True):
        _test(data_type, values, [True, False, TypeError, TypeError, TypeError, TypeError,TypeError,TypeError,TypeError])
