from __future__ import annotations

import rio
import ui_10x.platform_interface as i
from ui_10x.rio.component_builder import Layout


class BoxLayout(Layout): ...


class VBoxLayout(BoxLayout, i.VBoxLayout):
    s_component_class = rio.Column
    s_stretch_arg = 'grow_y'

    def _make_kwargs(self, **kwargs):
        kwargs = super()._make_kwargs(**kwargs)
        del kwargs['align_y']
        return kwargs


class HBoxLayout(BoxLayout, i.HBoxLayout):
    s_component_class = rio.Row
    s_stretch_arg = 'grow_x'


class FormLayout(Layout, i.FormLayout):
    s_component_class = rio.Grid
    s_children_attr = 'rows'

    def add_row(self, *args):
        self.add_children(args)

    def _build_children(self, session: rio.Session):
        return [[child(session) for child in children] for children in self._get_children()]  # children are 2d array
