import sys
from functools import partial
from http.cookiejar import debug
from types import NoneType
from typing import Type

import pytest

from core_10x.trait_method_error import TraitMethodError
from core_10x.code_samples.person import Person
from core_10x.exec_control import GRAPH_OFF, CONVERT_VALUES_OFF, DEBUG_ON, CONVERT_VALUES_ON
from core_10x.trait_definition import T
from core_10x.traitable import Traitable
from core_10x.ts_union import TsUnion
from core_10x.xnone import XNone, XNoneType


def _test_i( data_type: Type, values, expected_values):
    assert len(values)== len(expected_values)

    class TestableTraitable(Traitable):
        xid: int = T(T.ID, default=1)
        value: data_type = T(1) # noqa

    p = TestableTraitable(xid=1)
    for v, ev in zip(values, expected_values):
        if isinstance(ev, type) and issubclass(ev, Exception):
            try:
                p.value = v
            except Exception as ex:
                if not isinstance(ex, ev):
                    pytest.fail(f"Got {ex} instead of {ev} value {v} for type {data_type}")
            else:
                pytest.fail(f"Expected exception {ev} for value {v} for type {data_type}; converted to {p.value}")
        else:
            p.value = v
            assert p.value == ev
            if ev is None:
                with pytest.raises(ValueError):
                    p.serialize_object()
            else:
                ev = ev if ev is not XNone else None
                assert {'_id': '1', '_rev': 0, 'xid': 1, 'value': ev} == p.serialize_object()

def _test(data_type, values, expecte_types):
    with TsUnion(): # TODO: remove when db access is sorted
        _test_i(data_type, values, expecte_types)

def generic_test(data_type,values,convert_expected,allowed_types=()):
    allowed_types = (data_type,NoneType,XNoneType) + allowed_types
    debug_expected = [v if isinstance(v, allowed_types) else e if isinstance(e,Exception) else TypeError for v,e in zip(values,convert_expected)]
    _test(data_type, values, values)
    with DEBUG_ON():
        _test(data_type, values, debug_expected)
    with CONVERT_VALUES_ON():
        _test(data_type, values, convert_expected)
        with DEBUG_ON():
            _test(data_type, values, convert_expected)

def test_int_trait():
    data_type = int
    values = [180, 180.1, '180', 'abc', None, XNone, '']
    convert_expected = [180, 180, 180, TypeError, None, XNone, TypeError]
    generic_test(data_type,values,convert_expected)
    _test(data_type, values, values)

def test_float_trait():
    data_type = float
    values = [180, 180.1, '180', 'abc', None, XNone, '']
    convert_expected = [180.0, 180.1, 180.0, TypeError, None, XNone, TypeError]
    generic_test(data_type,values,convert_expected,(int,float))
    _test(data_type, values, values)

def test_bool_trait():
    data_type = bool
    values = [True, False, 1, 0, 'yes', 'no', 'abc', None, XNone, '', 'true','false','1','0','on','off']
    convert_expected = [True, False, True, False, True, False,TypeError,None,XNone,False,True,False,True,False,True,False]
    generic_test(data_type,values,convert_expected)

def test_date_trait():
    from datetime import datetime
    data_type = datetime
    values = [datetime(2020,1,1), '2020-01-01T00:00:00', '2020-01-01 00:00:00', '2020-01-01', 1577836800, None, XNone, 'abc', '', "Feb 1, 2020"]
    convert_expected = [datetime(2020,1,1), datetime(2020,1,1), datetime(2020,1,1), datetime(2020,1,1), TraitMethodError, None, XNone, TypeError, TypeError, datetime(2020,2,1)]
    generic_test(data_type,values,convert_expected)

