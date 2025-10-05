from __future__ import annotations

import inspect
from functools import partial
from typing import TYPE_CHECKING

import rio
import ui_10x.platform_interface as i
from ui_10x.rio.component_builder import Widget

if TYPE_CHECKING:
    from collections.abc import Callable


class Label(Widget, i.Label):
    s_component_class = rio.Text
    s_forced_kwargs = {'selectable': False}  # , 'align_x': 0}
    s_single_child = True
    s_children_attr = 'text'
    s_default_kwargs = {'text': ''}


class PushButton(Label, i.PushButton):
    s_component_class = rio.Button
    s_forced_kwargs = {}
    s_children_attr = 'content'
    s_default_kwargs = {'content': ''}

    def clicked_connect(self, bound_method: Callable[[bool], None]):
        unbound_params = [
            p.name for p in inspect.signature(bound_method).parameters.values() if p.default is p.empty and not p.kind.name.startswith('VAR_')
        ]
        assert len(unbound_params) < 2, f'Expected 0 or 1 unbound parameters in {bound_method.__name__}, but found {unbound_params}'
        if len(unbound_params) > 0:
            bound_method = partial(bound_method, False)
        self['on_press'] = self.callback(bound_method)

    def set_flat(self, flat: bool):
        self['style'] = 'plain-text' if flat else 'major'

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        if args:
            label = args[-1]
            assert label is not None
            icon = args[0] if len(args) > 1 else None
            self.set_text(label)
            self['icon'] = icon
