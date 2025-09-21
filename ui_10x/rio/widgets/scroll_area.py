from __future__ import annotations

from typing import Literal

from core_10x.named_constant import Enum

import rio
import ui_10x.platform_interface as i
from ui_10x.rio.component_builder import Widget


class SCROLL(Enum):
    OFF = 'never'
    ON = 'always'
    AS_NEEDED = 'auto'


class ScrollArea(Widget, i.ScrollArea):
    s_component_class = rio.ScrollContainer

    def set_widget(self, w: Widget):
        self.set_children([w])

    def set_horizontal_scroll_bar_policy(self, h):
        self._set_scrollbar_policy('scroll_x', h)

    def set_vertical_scroll_bar_policy(self, h):
        self._set_scrollbar_policy('scroll_y', h)

    def _set_scrollbar_policy(self, scroll: Literal['scroll_x', 'scroll_y'], policy: SCROLL):
        self[scroll] = policy.label
