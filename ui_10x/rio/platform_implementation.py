from __future__ import annotations

import asyncio

from core_10x.global_cache import cache

import ui_10x.platform_interface as i
from ui_10x.rio import component_builder, widgets


@cache
def init(): ...


class Object: ...


Application = widgets.Application


DirectConnection = component_builder.ConnectionType.DIRECT
QueuedConnection = component_builder.ConnectionType.QUEUED


BoundSignal = component_builder.BoundSignal


class signal_decl(i.signal_decl):
    """Match Qt ``pyqtSignal``: declare as class attribute, per-instance ``BoundSignal``."""

    __slots__ = ('_attr',)

    def __init__(self, arg=object):
        assert arg is object, 'arg must be object'

    def __set_name__(self, owner, name):
        self._attr = f'_signal_decl_{name}'

    def __get__(self, instance, owner):
        if instance is None:
            return self
        decl = vars(instance).get(self._attr)
        if decl is None:
            decl = BoundSignal()
            vars(instance)[self._attr] = decl
        return decl


MouseEvent = component_builder.MouseEvent


SCROLL = widgets.SCROLL

Point = component_builder.Point
FontMetrics = component_builder.FontMetrics
SizePolicy = component_builder.SizePolicy
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


def is_ui_thread() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True

