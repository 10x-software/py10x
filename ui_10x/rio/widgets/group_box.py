from __future__ import annotations

import ui_10x.platform_interface as i
import ui_10x.rio.components as rio_components
from ui_10x.rio.component_builder import Widget


class GroupBox(Widget, i.GroupBox):
    s_component_class = rio_components.GroupBox
    s_pass_children_in_kwargs = True
    s_unwrap_single_child = False

    def __init__(self, *args, **kwargs):
        _parent = None
        title = kwargs.pop('title', '')
        children = ()
        if len(args) == 1:
            _parent = args[0]
        elif len(args) >= 2:
            assert not title, 'title specified twice'
            _parent, title = args[:2]
            children = args[2:]
        super().__init__(*children, **kwargs)
        self['title'] = title

    def set_title(self, title: str):
        self['title'] = title
