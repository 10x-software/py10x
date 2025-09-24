import gc
from datetime import date
from functools import partial
from unittest.mock import MagicMock

import pytest
from core_10x.exec_control import BTP, INTERACTIVE
from core_10x.rc import RC
from core_10x.trait_method_error import TraitMethodError
from core_10x.traitable import Traitable
from more_itertools.more import side_effect


class X(Traitable):
    x: int
    y: int
    z: int

    def x_set(self, trait, value) -> RC:
        self.raw_set_value(trait,value)
        return self.set_values(y=value)

    def z_get(self):
        return self.x

def callback(btp, x, t, v):
    assert btp is BTP.current()
    #assert x.get_value(t) == v
    print(btp, BTP.current())
    x.bui_class().update_ui_node(x,t)

def test_ui_nodes():
    x = X(x=1)
    def t(ov, v):
        mx = MagicMock(side_effect=partial(callback, BTP.current(), x, x.T.x, v))
        my = MagicMock(side_effect=partial(callback, BTP.current(), x, x.T.y, v))
        mz = MagicMock(side_effect=partial(callback, BTP.current(), x, x.T.z, v))
        x.bui_class().create_ui_node(x, x.T.x, mx)
        x.bui_class().create_ui_node(x, x.T.y, my)
        x.bui_class().create_ui_node(x, x.T.z, mz)

        assert x.x == x.y == x.z == ov

        x.x=v

        assert mx.call_count == my.call_count ==  mz.call_count == 1
        assert x.x == x.y == x.z == v

        return mx,my,mz

    with INTERACTIVE() as i0:
        print(i0)
        mx,my,mz = t(1,2)
        with INTERACTIVE() as i:
            print(i)
            t(2,3)
        i.export_nodes()
        assert x.x == x.y == x.z == 3
        assert mx.call_count == my.call_count ==  mz.call_count == 2


def test_exception():
    def callback():
        x.bui_class().update_ui_node(x, x.T.x) #TODO: should not be required when throwing
        raise RuntimeError('test')

    x = X(x=1)
    with INTERACTIVE():
        m = MagicMock(side_effect=callback)
        x.bui_class().create_ui_node(x, x.T.x, m)
        with pytest.raises(TraitMethodError): #TODO: should be throwing RuntimeError?
            x.x = 2
        assert x.x == 2                       #TODO: should bot set value when callback failed?
        with INTERACTIVE() as i:
            x.x = 3
        with pytest.raises(RuntimeError):     #TODO: Runtime eroro or TraitMetodError?
            i.export_nodes()

        assert m.call_count == 2
