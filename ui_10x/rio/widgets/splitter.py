from __future__ import annotations

from core_10x.named_constant import Enum

import ui_10x.platform_interface as i
import ui_10x.rio.components as rio_components
from ui_10x.rio.component_builder import Widget


class Direction(Enum):
    VERTICAL = 'vertical'
    HORIZONTAL = 'horizontal'


Horizontal = Direction.HORIZONTAL


class Splitter(Widget, i.Splitter):
    s_component_class = rio_components.Splitter
    s_pass_children_in_kwargs = True

    def _make_kwargs(self, **kwargs):
        kwargs = super()._make_kwargs(**kwargs)
        if kwargs['direction'] == Horizontal.label:
            del kwargs['align_y']
            kwargs['grow_y'] = True
        kwargs['child_proportions'] = []
        return kwargs

    def __init__(self, direction: Direction = Horizontal, **kwargs):
        super().__init__(**kwargs | dict(direction=direction.label))

    def add_widget(self, widget: Widget):
        self.add_children(widget)
        self['child_proportions'].append(1)

    def set_handle_width(self, width: int):
        self['handle_size'] = width

    def set_stretch_factor(self, widget_index: int, factor: int):
        self['child_proportions'][widget_index] = factor  # TODO: normalize?

    def replace_widget(self, widget_index: int, widget: Widget):
        self.get_children()[widget_index] = widget
        self.force_update()
