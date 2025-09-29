from __future__ import annotations

from datetime import date

import rio
import ui_10x.platform_interface as i
from ui_10x.rio.component_builder import Widget


class CalendarWidget(Widget, i.CalendarWidget):
    s_component_class = rio.Calendar
    s_default_kwargs = dict(value=date.today())
    s_children_attr = 'value'
    s_single_child = True

    def set_grid_visible(self, grid_visible: bool):
        pass

    def set_selected_date(self, selected_date: date):
        self['value'] = selected_date

    def selected_date(self) -> date:
        return self['value']
