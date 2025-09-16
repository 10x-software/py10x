from __future__ import annotations

from collections.abc import Callable
from typing import Any

import ui_10x.platform_interface as i
import ui_10x.rio.components as rio_components
from ui_10x.rio.component_builder import Widget

# noinspection PyCompatibility
from . import (
    Application,
    Dialog,
    HBoxLayout,
    Label,
    PushButton,
    Style,
    VBoxLayout,
)


class Separator(Widget, i.Separator):
    s_component_class = rio_components.Separator
    s_forced_kwargs = {}

class MessageBox(i.MessageBox):
    @classmethod
    def _dialog(cls, parent: Widget, title: str, message: str, icon: Style.StandardPixmap, on_close: Callable[[Any],None]) -> bool|None:
        style = Application.style()
        if icon==Style.StandardPixmap.SP_MESSAGEBOXQUESTION:
            buttons = [
                PushButton(style.standard_icon(Style.StandardPixmap.SP_DIALOGYESBUTTON.value), 'Yes', on_press=lambda: dlg.on_accept()),
                PushButton(style.standard_icon(Style.StandardPixmap.SP_DIALOGNOBUTTON.value), 'No', on_press=lambda: dlg.on_reject())
            ]
        else:
            buttons = [
                PushButton(style.standard_icon(Style.StandardPixmap.SP_DIALOGOKBUTTON.value), 'Ok', on_press=lambda: dlg.on_accept())
            ]
        children = (
            Label(title,align_x=0.5,align_y=0,style='heading1'),
            Separator(),
            HBoxLayout(
                PushButton(style.standard_icon(icon.value),'', style='plain-text', is_sensitive=False, align_y=0, align_x=0, grow_x=False),
                Label(message, align_y=0, overflow='wrap', grow_x=True)),
            Separator(),
            HBoxLayout(*buttons),
        )
        dlg = Dialog(parent=parent, title=title, children=children,
                           on_accept=lambda: on_close(dlg.accepted),
                           on_reject=lambda: on_close(dlg.accepted))
        dlg.set_layout(VBoxLayout())
        return dlg.show() if on_close else dlg.exec()

    @classmethod
    def question(cls, parent: Widget, title: str, message: str, on_close: Callable[[Any],None]) -> bool:
        return cls._dialog(parent=parent,title=title,message=message,icon=Style.StandardPixmap.SP_MESSAGEBOXQUESTION,on_close=on_close)

    @classmethod
    def warning(cls, parent: Widget, title: str, message: str, on_close: Callable[[Any],None]):
        return cls._dialog(parent=parent,title=title,message=message,icon=Style.StandardPixmap.SP_MESSAGEBOXWARNING,on_close=on_close)

    @classmethod
    def information(cls, parent: Widget, title: str, message: str, on_close: Callable[[Any],None]):
        return cls._dialog(parent=parent,title=title,message=message,icon=Style.StandardPixmap.SP_MESSAGEBOXINFORMATION,on_close=on_close)

    @classmethod
    def is_yes_button(cls, sb) -> bool:
        return sb