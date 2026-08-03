from __future__ import annotations

from functools import partial
from unittest.mock import MagicMock

import pytest
from core_10x.exec_control import BTP, INTERACTIVE
from core_10x.rc import RC
from core_10x.trait_method_error import TraitMethodError
from core_10x.traitable import Traitable


class X(Traitable):
    x: int
    y: int
    z: int

    def x_set(self, trait, value) -> RC:
        self.raw_set_trait_value(trait, value)
        return self.set_values(y=value)

    def z_get(self):
        return self.x


def callback(data):
    # Mutable bag holds bind-time BTP (and x/trait/v) so call-time can assert
    # identity; bags are cleared after the test so partials do not pin
    # INTERACTIVE BTP / x (hybrid C++/Python cycles are not GC-breakable yet).
    btp, x, t, v = data
    assert btp is BTP.current()
    # assert x.get_trait_value(t) == v
    print(btp, BTP.current())
    x.bui_class().update_ui_node(x, t)


def test_ui_nodes():
    x = X(x=1)
    # TODO(gc): drop bags + data.clear() once BTP/XCache/UI nodes participate in
    # cyclic GC and can break partial→BTP→cache→UI node→partial without help
    # (see test_graph_leaks module docstring). Keep bagging only if we still need
    # an explicit bind-time BTP for the callback identity assert.
    bags: list[list] = []

    def t(ov, v):
        def make(trait):
            data = [BTP.current(), x, trait, v]
            bags.append(data)
            return MagicMock(side_effect=partial(callback, data))

        mx = make(x.T.x)
        my = make(x.T.y)
        mz = make(x.T.z)
        x.bui_class().create_ui_node(x, x.T.x, mx)
        x.bui_class().create_ui_node(x, x.T.y, my)
        x.bui_class().create_ui_node(x, x.T.z, mz)

        assert x.x == x.y == x.z == ov

        x.x = v

        assert mx.call_count == my.call_count == mz.call_count == 1
        assert x.x == x.y == x.z == v

        return mx, my, mz

    with INTERACTIVE() as i0:
        print(i0)
        mx, my, mz = t(1, 2)
        with INTERACTIVE() as i:
            print(i)
            t(2, 3)
        i.export_nodes()
        assert x.x == x.y == x.z == 3
        assert mx.call_count == my.call_count == mz.call_count == 2

    for data in bags:
        data.clear()  # TODO(gc): remove when hybrid cycles are GC-breakable


def test_exception():
    def callback():
        x.bui_class().update_ui_node(x, x.T.x)  # TODO: should not be required when throwing
        raise RuntimeError('test')

    x = X(x=1)
    with INTERACTIVE():
        m = MagicMock(side_effect=callback)
        x.bui_class().create_ui_node(x, x.T.x, m)
        with pytest.raises(TraitMethodError):  # TODO: should be throwing RuntimeError?
            x.x = 2
        assert x.x == 2  # TODO: should not set value when callback failed?
        with INTERACTIVE() as i:
            x.x = 3
        with pytest.raises(RuntimeError):  # TODO: RuntimeError or TraitMethodError?
            i.export_nodes()

        assert m.call_count == 2
