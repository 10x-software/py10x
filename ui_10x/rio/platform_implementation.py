from __future__ import annotations

import asyncio
from collections.abc import Callable

from core_10x.global_cache import cache
from core_10x.named_constant import Enum

from ui_10x.rio import component_builder, widgets


@cache
def init(): ...


class Object: ...


Application = widgets.Application


class ConnectionType(Enum):
    DIRECT = ()
    QUEUED = ()


DirectConnection = ConnectionType.DIRECT
QueuedConnection = ConnectionType.QUEUED


class SignalDecl:
    def __init__(self):
        self.handlers: set[tuple[Callable[[...], None], ConnectionType]] = set()

    def connect(self, handler: Callable[[...], None], type: ConnectionType = QueuedConnection) -> bool:
        self.handlers.add((handler, type))
        return True

    def emit(self, *args) -> None:
        for handler, conn in self.handlers:
            handler(*args) if conn == DirectConnection else asyncio.get_running_loop().call_soon(handler, *args)


def signal_decl(arg=object):
    assert arg is object, 'arg must be object'
    return SignalDecl()


class MouseEvent: ...


SCROLL = widgets.SCROLL

Point = component_builder.Point
FontMetrics = component_builder.FontMetrics
SizePolicy = component_builder.FontMetrics
TEXT_ALIGN = component_builder.TEXT_ALIGN

Widget = component_builder.Widget
Layout = component_builder.Layout
FlowLayout = component_builder.FlowLayout

LineEdit = widgets.LineEdit
Label = widgets.Label
PushButton = widgets.PushButton

Spacer = widgets.Spacer

HBoxLayout = widgets.HBoxLayout
VBoxLayout = widgets.VBoxLayout
FormLayout = widgets.FormLayout

Dialog = widgets.Dialog

MessageBox = widgets.MessageBox

RadioButton = widgets.RadioButton
ButtonGroup = widgets.ButtonGroup

GroupBox = widgets.GroupBox

TextEdit = widgets.TextEdit
CheckBox = widgets.CheckBox
ScrollArea = widgets.ScrollArea
Separator = widgets.Separator


def separator(horizontal=True) -> Separator:
    return Separator() if horizontal else Separator(orientation='vertical')


Direction = widgets.Direction

Vertical = Direction.VERTICAL
Horizontal = Direction.HORIZONTAL

Splitter = widgets.Splitter

Style = widgets.Style

FindFlags = widgets.FindFlags
MatchExactly = FindFlags.MATCH_EXACTLY

ListWidget = widgets.ListWidget
ListItem = widgets.ListItem

TreeWidget = widgets.TreeWidget
TreeItem = widgets.TreeItem

CalendarWidget = widgets.CalendarWidget
