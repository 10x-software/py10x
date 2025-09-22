from __future__ import annotations

import ui_10x.platform_interface as i
import ui_10x.rio.components as rio_components
from ui_10x.rio.component_builder import Widget


class GroupBox(Widget, i.GroupBox):
    s_component_class = rio_components.GroupBox
    s_pass_children_in_kwargs = True

    def __init__(self, *args, **kwargs):
        parent = None
        title = kwargs.pop('title', '')
        children = ()
        if len(args) >= 1:
            parent = args[0]
        if len(args) >= 2:
            assert not title, 'title specified twice'
            parent, title = args  # noqa: RUF059 - review
            children = args[2:]
        super().__init__(*children, **kwargs)
        self['title'] = title

    def set_title(self, title: str):
        self['title'] = title
