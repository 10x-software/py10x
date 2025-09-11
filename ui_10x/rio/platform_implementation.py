from __future__ import annotations

import asyncio
import inspect
from typing import Any, TYPE_CHECKING
from datetime import date

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import KW_ONLY, dataclass
from functools import partial
from typing import Self, Literal

import rio

import ui_10x.platform_interface as i
import ui_10x.rio.components as rio_components
from core_10x.global_cache import cache
from core_10x.named_constant import Enum, EnumBits, NamedConstant
from ui_10x.platform_interface import Style

if TYPE_CHECKING:
    import uvicorn

CURRENT_SESSION: rio.Session | None = None
@contextmanager
def session_context(session: rio.Session):
    global CURRENT_SESSION
    assert CURRENT_SESSION is None
    CURRENT_SESSION = session
    try:
        yield
    finally:
        CURRENT_SESSION = None

@cache
def init() -> rio.App:
    ...

class Object:
    ...

class Application(i.Application):
    @classmethod
    def instance(cls) -> 'Application':
        raise NotImplementedError()

    @classmethod
    def style(cls):
        return Style()

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

    def emit(self,*args) -> None:
        for handler, conn in self.handlers:
            handler(*args) if conn == DirectConnection else asyncio.get_running_loop().call_soon(handler,*args)

def signal_decl(arg=object):
    assert arg is object, 'arg must be object'
    return SignalDecl()

class MouseEvent:
    ...

class TEXT_ALIGN(NamedConstant):
    s_vertical = 0xf << 4

    LEFT = 1
    CENTER = 6
    RIGHT = 11
    TOP = LEFT << 4
    V_CENTER = CENTER << 4
    BOTTOM = RIGHT << 4

    @classmethod
    def from_str(cls, s: str) -> TEXT_ALIGN:
        return super().from_str(s.upper()) # type: ignore[return-value]

    def rio_attr(self) -> str:
        return 'align_y' if self.value & self.s_vertical else 'align_x'

    def rio_value(self) -> float:
        return ((self.value >> 4 if self.value & self.s_vertical else self.value)-1) /10

class SCROLL(Enum):
    OFF = 'never'
    ON = 'always'
    AS_NEEDED = 'auto'

class SizePolicy(Enum):
    MINIMUM_EXPANDING = ()

    MinimumExpanding = MINIMUM_EXPANDING #TODO...

class _WidgetMixin:
    __slots__ = ()
    def set_style_sheet(self, sh: str):
        from ui_10x.utils import UxStyleSheet #TODO: circular import
        sh = UxStyleSheet.loads(sh)
        if text_align:=TEXT_ALIGN.from_str(sh.pop('text-align', '')):
            self[text_align.rio_attr()] =text_align.rio_value()

        #TODO: implement other style sheet properties

    def set_minimum_height(self, height: int):
        self['min_height'] = height

    def set_minimum_width(self, width: int):
        self['min_width'] = width

    def set_size_policy(self, x_policy, y_policy):
        assert y_policy == x_policy == SizePolicy.MinimumExpanding, 'only expanding size policy supported'
        self['grow_x'] = True
        self['grow_y'] = True

    def set_layout(self, layout: i.Layout):
        raise NotImplementedError

class DynamicComponent(rio.Component):
    builder: ComponentBuilder
    _=KW_ONLY
    revision: int = 0

    def __init__(self, builder: ComponentBuilder, revision: int=0):
        super().__init__()
        self.key = id(self)
        self.builder = builder
        self.revision = revision

    def build(self) -> rio.Component:
        _=self.revision
        return self.builder.build(self.session)

class ComponentBuilder:
    __slots__ = ('component','_kwargs')

    s_component_class : type[rio.Component] = None
    s_forced_kwargs = {}
    s_default_kwargs = {}
    s_dynamic = True
    s_children_attr = 'children'
    s_single_child = False
    s_size_adjustments = ('min_width', 'min_height', 'margin_left', 'margin_top', 'margin_right', 'margin_bottom')

    def _get_children(self):
        children = self[self.s_children_attr]
        if self.s_single_child and children is None:
            return []
        return [children] if self.s_single_child else children

    def _set_children(self,children):
        if self.s_single_child and not children:
            self[self.s_children_attr] = None
        else:
            assert not self.s_single_child or len(children) == 1
            self[self.s_children_attr] = children[0] if self.s_single_child else children

    def __init__(self, *children, **kwargs):
        assert self.s_component_class, f"{self.__class__.__name__}: has no s_component_class"
        defaults = {kw:value(kwargs) if callable(value) else value for kw,value in self.s_default_kwargs.items()}
        self._kwargs = defaults | kwargs | self.s_forced_kwargs
        self.component = None
        kw_kids = self._kwargs.get(self.s_children_attr)
        if self.s_single_child:
            self._set_children(children if children else [kw_kids])
        else:
            self._set_children([])
            self.add_children(*children)
            if kw_kids is not None:
                self.add_children(*kw_kids)

    def add_children(self, *children):
        existing_children = set(self._get_children())
        if self.s_single_child:
            new_children = [child for child in children if child is not None and child not in existing_children]
            if new_children:
                assert not existing_children
                self._set_children(new_children)
        else:
            self[self.s_children_attr].extend(child for child in children if child is not None and child not in existing_children)
        self.force_update()
        
    def with_children(self, *args):
        return self.__class__(*args,**self._kwargs) if args else self

    def _build_children(self,session: rio.Session):
        return [ child(session) if isinstance(child,ComponentBuilder) else child for child in self._get_children() if child is not None]

    def build(self,session):
        kwargs = {k: v for k, v in self._kwargs.items() if k != self.s_children_attr}
        for size_adjustment in self.s_size_adjustments:
            if size_adjustment in kwargs:
                kwargs[size_adjustment] = kwargs[size_adjustment] / session.pixels_per_font_height
        return self.s_component_class(*self._build_children(session), **kwargs)

    def __call__(self,session: rio.Session) -> rio.Component:
        self.component = DynamicComponent(self) if self.s_dynamic else self.build(session)
        return self.component

    def __getitem__(self, item):
        #TODO: two way mapping..
        #if self.component and self.component._build_data_:
        #    return getattr(self.component._build_data_.build_result,item)
        return self._kwargs[item]

    def __contains__(self,item):
        return item in self._kwargs

    def __setitem__(self, item, value):
        self._kwargs[item] = value
        self.force_update()

    def force_update(self):
        component: rio.Component = self.component
        if component:
            component.revision = component.revision + 1
            component.force_refresh()

    def setdefault(self, item, default):
        try:
            value = self[item]
        except KeyError:
            value = self[item] = default
        return value

    def callback(self,callback):
        def cb(*args,**kwargs):
            with session_context(self.component.session):
                # note - callback must not yield the event loop!
                return callback(*args,**kwargs)
        return cb

@dataclass
class Point(i.Point):
    _x: int = 0
    _y: int = 0

    def x(self) -> int:
        return self._x

    def y(self) -> int:
        return self._y

class FontMetrics(i.FontMetrics):
    __slots__ = ('_widget',)
    def __init__(self, w: Widget):
        self._widget = w

    def average_char_width(self) -> int:
        return 1 # best guess -- rio measures sizes in char heights

class Widget(ComponentBuilder, _WidgetMixin, i.Widget):
    s_component_class = rio.Container
    s_stretch_arg = 'grow_x'
    s_default_layout_factory = lambda: FlowLayout()

    __slots__ = ('_layout',)

    def __init_subclass__(cls, **kwargs):
        cls.s_default_layout_factory = None
    
    def __init__(self, *children, **kwargs):
        super().__init__(*children, **kwargs)
        layout_factory = self.__class__.s_default_layout_factory
        self._layout = layout_factory() if layout_factory else None
        
    def set_layout(self, layout: i.Layout):
        self._layout = layout
        
    def _build_children(self,session: rio.Session):
        return [self._layout.with_children(*self._get_children()).build(session)] if self._layout else super()._build_children(session)

    def set_stretch(self, stretch):
        assert stretch in (0, 1), 'Only stretch of 0 or 1 is currently supported'
        self[self.s_stretch_arg] = bool(stretch)

    def style_sheet(self) -> str:
        return "" #TODO...

    def set_enabled(self, enabled: bool):
        self['is_sensitive'] = enabled

    def set_tool_tip(self, tooltip):
        ... #TODO

    def font_metrics(self) -> FontMetrics:
        return FontMetrics(self)

    #placeholders
    def set_geometry(self, *args):
        pass

    def width(self) -> int:
        return 0

    def height(self) -> int:
        return 0

    def map_to_global(self, point: Point) -> Point:
        return point

class Label(Widget, i.Label):
    s_component_class = rio.Text
    s_forced_kwargs = {'selectable': False}#, 'align_x': 0}
    s_default_kwargs = {'text': ''}
    s_single_child = True
    s_children_attr = 'text'

    def set_text(self, text: str):
        self['text'] = text or ''

class PushButton(Label,i.PushButton):
    s_component_class = rio.Button
    s_forced_kwargs = {}

    def clicked_connect(self, bound_method:Callable[[bool]]):
        unbound_params = [p.name for p in inspect.signature(bound_method).parameters.values() if p.default is p.empty and not p.kind.name.startswith('VAR_')]
        assert len(unbound_params) < 2, f"Expected 0 or 1 unbound parameters in {bound_method.__name__}, but found {unbound_params}"
        if len(unbound_params)>0:
            bound_method = partial(bound_method,False)
        self['on_press'] = self.callback(bound_method)

    def set_flat(self, flat: bool):
        self['style'] = 'plain-text' if flat else 'major'

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        if args:
            label = args[-1]
            assert label is not None
            icon = args[0] if len(args)>1 else None
            self['text'] = label
            self['icon'] = icon


class Layout(Widget, i.Layout):
    def add_widget(self, widget: Widget, stretch=None, **kwargs):
        assert not kwargs, f'kwargs not supported: {kwargs}'
        assert widget is not None
        if stretch is not None:
            widget.set_stretch(stretch)
        self[self.s_children_attr].append(widget)

    def add_layout(self, layout: Layout, stretch=None, **kwargs):
        self.add_widget(layout, stretch=stretch, **kwargs)

    def set_spacing(self, spacing: int):
        assert spacing == 0, 'Only zero is supported'
        self['spacing'] = 0

    def set_contents_margins(self, left, top, right, bottom):
        self['margin_left'] = left
        self['margin_top'] = top
        self['margin_right'] = right
        self['margin_bottom'] = bottom

class VBoxLayout(Layout, i.VBoxLayout):
    s_component_class = rio.Column
    s_stretch_arg = 'grow_y'

class HBoxLayout(Layout,i.HBoxLayout):
    s_component_class = rio.Row
    s_stretch_arg = 'grow_x'

class FlowLayout(Layout, i.Layout):
    s_component_class = rio.FlowContainer

class FormLayout(Layout,i.FormLayout):
    s_component_class = rio.Grid
    s_children_attr = 'rows'

    def add_row(self, *args):
        self.add_children(args)

    def _build_children(self,session: rio.Session):
        return [[child(session) for child in children] for children in self._get_children()]

class Dialog(Widget,i.Dialog):
    __slots__ = ('_dialog','_parent','_server','_modal')
    s_component_class = rio.Column
    s_forced_kwargs = {'grow_x': True, 'grow_y': True}

    def __init__(self, parent: Widget|None = None, children=(), title=None, on_accept=None, on_reject=None, **kwargs):
        assert isinstance(parent,Widget|None)
        super().__init__(*children, **kwargs)
        self.on_accept = self._wrapper(on_accept, accept=True)
        self.on_reject = self._wrapper(on_reject)
        self.accepted = True
        self.title = title
        self._dialog = None
        self._server = None
        self._parent = parent
        self._modal = True

    def set_window_title(self, title: str):
        self.title = title

    def _wrapper(self, func, accept = False):
        func = self.callback(func) if func else None
        def wrapper(*args):
            self.accepted = accept
            if func:
                func(*args)
            self._on_close()
        return wrapper

    def reject(self):
        self._on_close()

    def done(self, result: int):
        self._on_close()
        self.accepted = bool(result)

    def _on_close(self):
        if self._dialog:
            dialog = self._dialog.result()
            dialog._root_component.session.create_task(dialog.close())
            self._dialog = None
        elif self._server:
            self._server.should_exit = True

    def _on_server_created(self, server: uvicorn.Server):
        self._server = server

    def _on_dialog_open(self,future):
        self._dialog = future

    def exec(self):
        assert not CURRENT_SESSION, 'Cannot start another event loop - use show() with callbacks instead'
        title = self.title or 'Dialog'
        app = rio.App(name=title, build=lambda : DynamicComponent(self))
        assert not self._parent
        debug = True
        if debug:
            from rio.debug.monkeypatches import apply_monkeypatches
            apply_monkeypatches()
        #app._run_in_window(debug_mode=debug,on_server_created=self._on_server_created)
        app._run_as_web_server(debug_mode=debug)
        return self.accepted

    def show(self):
        if not CURRENT_SESSION:
            self.exec()
        else:
            future = CURRENT_SESSION.show_custom_dialog(build=self, on_close=self._on_close, modal=self._modal, owning_component=self._parent.component if self._parent else None)
            CURRENT_SESSION.create_task(future).add_done_callback(self._on_dialog_open)

    def set_window_flags(self, flags):
        raise NotImplementedError

    def set_modal(self, modal: bool):
        self._modal = modal

class MessageBox(i.MessageBox):
    @classmethod
    def _dialog(cls, parent: Widget, title: str, message: str, icon: Style.StandardPixmap, on_close: Callable[[Any],None]) -> bool:
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
        if not on_close:
            return dlg.exec()
        dlg.show()

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


class RadioButton(Widget, i.RadioButton):
    __slots__ = ('_button_group')
    s_component_class = rio_components.RadioButton
    s_dynamic = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'label' not in self._kwargs:
            self['label'] = self['children'].pop(0)
        if 'selected_value' not in self._kwargs:
            self['selected_value'] = None
        if 'value' not in self._kwargs:
            self['value'] = self._kwargs['label']
        self['on_select']=self.on_select
        self._button_group = None

    def set_checked(self, checked: bool):
        self['selected_value'] = self['value'] if checked else None
        if checked and self._button_group:
            self._button_group['selected_value'] = self['value']

    def on_select(self, value):
        if self._button_group:
            self._button_group.on_change(value)

    def __call__(self, session: rio.Session) -> rio.Component:
        button = super().__call__(session)
        if self._button_group:
            self._button_group._buttons.append(button)
        return button

class ButtonGroup(Widget, i.ButtonGroup):
    __slots__ = ('_buttons',)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._buttons = []

    def on_change(self, value):
        self['selected_value'] = value
        for button in self._buttons:
            button.selected_value = value

    def add_button(self, button, id):
        if id < len(self['children']):
            self['children'][id] = button
        else:
            assert len(self['children']) == id
            self['children'].append(button)
        if button['selected_value'] == button['value']:
            self['selected_value'] = button['value']
        button._button_group = self

    def button(self, id: int) -> RadioButton:
        return self['children'][id]

    def checked_id(self):
        #TODO: optimize
        selected = self['selected_value']
        for i, button in enumerate(self['children']):
            if button['value'] == selected:
                return i
        return -1


class GroupBox(Widget, i.GroupBox):
    s_component_class = rio_components.GroupBox
    def __init__(self, *args, **kwargs):
        parent = None
        title = kwargs.pop('title', '')
        children = ()
        if len(args) >= 1:
            parent = args[0]
        if len(args) >= 2:
            assert not title, 'title specified twice'
            parent, title = args
            children = args[2:]
        super().__init__(*children, **kwargs)
        self['title'] = title

    def set_title(self, title: str):
        self['title'] = title

class LineEditComponent(rio.Component):
    text: str
    tooltip: str | None = None
    is_sensitive: bool = True
    on_change: rio.EventHandler[[str]] = None
    on_confirm: rio.EventHandler[[str]] = None

    def build(self):
        text_input = rio.TextInput(
                self.text,  #self.bind().text,
                is_sensitive = self.is_sensitive,
                on_change = self.on_change,
                on_confirm = self.on_confirm
            )

        if self.tooltip is None:
            return text_input

        tooltip = rio.Tooltip(
            text_input,
            self.tooltip
        )
        return rio.Stack(tooltip, text_input)

class LineEdit(Widget, i.LineEdit):
    s_default_kwargs = dict(text='')
    s_component_class = LineEditComponent
    s_single_child = True
    s_children_attr = 'text'
    def set_text(self, text: str):
        self['text'] = text or ''

    def set_tool_tip(self, tooltip: str):
        self['tooltip'] = tooltip

    def text(self):
        if self.component:
            #TODO: this if statement should not be necessary - debug why self.bind().text is not sufficient.
            return self.component._build_data_.build_result._build_data_.build_result.children[1].text
        return self['text']

    def text_edited_connect(self, bound_method):
        self['on_change'] = self.callback(lambda ev: bound_method(ev.text))

    def set_read_only(self, read_only: bool):
        self['is_sensitive'] = not read_only

    def set_password_mode(self):
        self['is_password'] = True

    def editing_finished_connect(self, bound_method):
        self['on_confirm'] = self.callback(lambda ev: bound_method())

class TextEdit(Widget, i.TextEdit):
    s_component_class = rio.MultiLineTextInput
    def to_plain_text(self) -> str:
        return self['text']
    def set_plain_text(self, text: str):
        self['text'] = text
    def set_read_only(self, readonly: bool):
        self['is_sensitive'] = not readonly

class LabeledCheckBox(rio.Component):
    label: str = ''
    is_on: bool = False
    def build(self):
        return rio.Row(rio.Text(self.label),rio.CheckBox(is_on=self.bind().is_on))

class CheckBox(Widget, i.CheckBox):
    s_component_class = LabeledCheckBox

    def set_checked(self, checked: bool):
        self["is_on"] = checked

    def is_checked(self) -> bool:
        return self["is_on"]

    def state_changed_connect(self, bound_method):
        def state_change_handler(event):
            bound_method(event.is_on)
        self["on_change"] = self.callback(state_change_handler)

    def set_text(self, text: str):
        self["label"] = text

class ScrollArea(Widget, i.ScrollArea):
    s_component_class = rio.ScrollContainer
    def set_widget(self, w: Widget):
        self['children'] = [w]

    def set_horizontal_scroll_bar_policy(self, h):
        self._set_scrollbar_policy('scroll_x',h)

    def set_vertical_scroll_bar_policy(self, h):
        self._set_scrollbar_policy('scroll_y',h)

    def _set_scrollbar_policy(self,scroll:Literal['scroll_x','scroll_y'],policy:SCROLL):
        self[scroll] = policy.label

class Separator(Widget, i.Separator):
    s_component_class = rio_components.Separator
    s_forced_kwargs = {}

def separator(horizontal = True) -> Separator:
    return Separator() if horizontal else Separator(orientation='vertical')

class Direction(Enum):
    VERTICAL = 'vertical'
    HORIZONTAL = 'horizontal'

Vertical = Direction.VERTICAL
Horizontal = Direction.HORIZONTAL

class Splitter(Widget, i.Splitter):
    s_component_class = rio_components.Splitter

    def __init__(self, direction: Direction=Horizontal, **kwargs):
        super().__init__(**kwargs)
        self['direction']=direction.label
        self['child_proportions']=[]

    def add_widget(self, widget: Widget):
        self.add_children(widget)
        self['child_proportions'].append(1)

    def set_handle_width(self, width: int):
        self['handle_size'] = width

    def set_stretch_factor(self, widget_index: int, factor: int):
        self['child_proportions'][widget_index] = factor #TODO: normalize?

    def replace_widget(self, widget_index: int, widget: Widget):
        self['children'][widget_index] = widget
        self.force_update()


class Style(i.Style):
    class EnumMeta(type):
        def __getattr__(cls, value):
            if value != value.upper():
                return getattr(cls, value.upper()).value

    class StandardPixmap(EnumBits, metaclass=EnumMeta):
        """Mapping of Qt QStyle::StandardPixmap values to Material Icons."""
        # Dialog Buttons
        SP_DIALOGAPPLYBUTTON = ("done",)
        SP_DIALOGCANCELBUTTON = ("close",)
        SP_DIALOGCLOSEBUTTON = ("close",)
        SP_DIALOGDISCARDBUTTON = ("close",)
        SP_DIALOGHELPBUTTON = ("help_outline",)
        SP_DIALOGNOBUTTON = ("close",)
        SP_DIALOGOKBUTTON = ("check",)
        SP_DIALOGOPENBUTTON = ("folder_open",)
        SP_DIALOGRESETBUTTON = ("restart_alt",)
        SP_DIALOGSAVEBUTTON = ("save",)
        SP_DIALOGYESBUTTON = ("check",)
        # Arrows and Navigation
        SP_ARROWBACK = ("arrow_back",)
        SP_ARROWDOWN = ("arrow_downward",)
        SP_ARROWFORWARD = ("arrow_forward",)
        SP_ARROWLEFT = ("arrow_left",)
        SP_ARROWRIGHT = ("arrow_right",)
        SP_ARROWUP = ("arrow_upward",)
        # File System and Folders
        SP_DIRCLOSEDICON = ("folder",)
        SP_DIRHOMEICON = ("home",)
        SP_DIRICON = ("folder",)
        SP_DIRLINKICON = ("folder_special",)
        SP_DIROPENICON = ("folder_open",)
        SP_FILEDIALOGBACK = ("arrow_back",)
        SP_FILEDIALOGCONTENTSVIEW = ("view_list",)
        SP_FILEDIALOGDETAILEDVIEW = ("grid_view",)
        SP_FILEDIALOGEND = ("last_page",)
        SP_FILEDIALOGINFOVIEW = ("info",)
        SP_FILEDIALOGLISTVIEW = ("list",)
        SP_FILEDIALOGNEWFOLDER = ("create_new_folder",)
        SP_FILEDIALOGSTART = ("first_page",)
        SP_FILEDIALOGTOPARENT = ("arrow_upward",)
        SP_FILEICON = ("description",)
        SP_FILELINKICON = ("insert_link",)
        # Drives and Devices
        SP_COMPUTERICON = ("computer",)
        SP_DESKTOPICON = ("desktop_windows",)
        SP_DRIVECDICON = ("album",)
        SP_DRIVEDVDICON = ("album",)
        SP_DRIVEFDICON = ("save",)
        SP_DRIVEHDICON = ("storage",)
        SP_DRIVENETICON = ("cloud",)
        SP_HOMEICON = ("home",)
        SP_TRASHICON = ("delete",)
        # Media Controls
        SP_MEDIAPAUSE = ("pause",)
        SP_MEDIAPLAY = ("play_arrow",)
        SP_MEDIASEEKBACKWARD = ("fast_rewind",)
        SP_MEDIASEEKFORWARD = ("fast_forward",)
        SP_MEDIASKIPBACKWARD = ("skip_previous",)
        SP_MEDIASKIPFORWARD = ("skip_next",)
        SP_MEDIASTOP = ("stop",)
        SP_MEDIAVOLUME = ("volume_up",)
        SP_MEDIAVOLUMEMUTED = ("volume_off",)
        # Message Boxes
        SP_MESSAGEBOXCRITICAL = ("error",)
        SP_MESSAGEBOXINFORMATION = ("info",)
        SP_MESSAGEBOXQUESTION = ("help",)
        SP_MESSAGEBOXWARNING = ("warning",)
        # Browser Controls
        SP_BROWSERRELOAD = ("refresh",)
        SP_BROWSERSTOP = ("stop",)
        # Title Bar and Window Controls
        SP_TITLEBARCLOSEBUTTON = ("close",)
        SP_TITLEBARCONTEXTHELPBUTTON = ("help_outline",)
        SP_TITLEBARMAXBUTTON = ("maximize",)
        SP_TITLEBARMENUBUTTON = ("menu",)
        SP_TITLEBARMINBUTTON = ("minimize",)
        SP_TITLEBARNORMALBUTTON = ("restore",)
        SP_TITLEBARSHADEBUTTON = ("expand_less",)
        SP_TITLEBARUNSHADEBUTTON = ("expand_more",)
        # Toolbar and Dock Widgets
        SP_DOCKWIDGETCLOSEBUTTON = ("close",)
        SP_TOOLBARHORIZONTALEXTENSIONBUTTON = ("chevron_right",)
        SP_TOOLBARVERTICALEXTENSIONBUTTON = ("chevron_down",)
        # Platform-Specific
        SP_COMMANDLINK = ("arrow_right_alt",)
        SP_VISTASHIELD = ("security",)

    def standard_icon(self, style_icon: int):
        return f"material/{self.StandardPixmap.s_reverse_dir[style_icon].label}"

class ListItem(Widget, i.ListItem):
    __slots__ = ('_list_widget',)
    s_component_class = rio.SimpleListItem
    s_default_kwargs = dict(key=lambda kwargs:kwargs['text'])
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._list_widget = None

    def row(self):
        if self._list_widget:
            return self._list_widget.row(self)

    def set_selected(self, selected: bool):
        return self._list_widget.set_selected(self, selected)

class FindFlags(Enum):
    MATCH_EXACTLY = ()

MatchExactly = FindFlags.MATCH_EXACTLY

class ListWidget(Widget, i.ListWidget):
    s_component_class = rio.ListView
    s_default_kwargs = dict(selection_mode='single')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_items(self, items: [ListItem|str]):
        for item in items:
            self.add_item(item)

    def clicked_connect(self, bound_method):
        self._on_press = self.callback(bound_method)

    def _handle_on_press(self, item):
        if self._on_press:
            self._on_press(item)

    def add_item(self, item: ListItem|str):
        item = ListItem(text=item) if isinstance(item,str) else item
        item['on_press'] = partial(self._handle_on_press, item)
        item._list_widget = self
        self['children'] = self.setdefault('children',[]) + [item]

    def clear(self):
        self['children'] = []

    def find_items(self, text, flags):
        assert flags == MatchExactly, 'only MatchExactly supported'
        return [item for item in self._kwargs['children'] if text == item['text']]

    def row(self, item: ListItem) -> int:
        return self._kwargs['children'].index(item)

    def take_item(self, row: int):
        try:
            return self._kwargs['children'].pop(row)
        finally:
            self.force_update()

    def set_selected(self, item: ListItem, selected: bool):
        #TODO: this is called from on-click handler for list item, which is
        # inefficient and duplicates rio built-in functionality
        selected_items = self.setdefault('selected_items',[])
        key = item['key']
        old_selected = key in selected_items
        print(selected_items, selected, old_selected, key)

        if not old_selected and selected:
            if self['selection_mode'] == 'single':
                selected_items = []
            selected_items.append(key)

        if old_selected and not selected:
            selected_items.remove(key)
        print(selected_items)
        self['selected_items'] = selected_items


class RioTreeItemBase(rio.Component):
    """ same as SimpleTreeItem, but includes tooltip and supports double-click """
    text: str = ''
    on_double_press: rio.EventHandler[[]] = None
    on_press: rio.EventHandler[[]] = None
    on_change: rio.EventHandler[[]] = None
    tooltip: str|None = None
    editable: bool = False
    editing: bool = False
    children: list[Self] = []
    is_expanded: bool = False

    def build_primary_text(self):
        if not self.editing:
            return rio.Text(self.text, justify="left", selectable=False)
        return rio.TextInput(
            self.text,
            justify="left",
            on_confirm=self.handle_edit_confirm
        )

    def build_content(self):
        content = self.build_primary_text()
        if self.tooltip:
            content = rio.Row( content,
                        rio.Tooltip(
                            anchor = content,
                            tip = self.tooltip
                        )
           )
        if self.on_double_press:
            content = rio.PointerEventListener( content,
                on_double_press=self.handle_double_press
            )
        return content

    def handle_double_press(self, ev: rio.PointerEvent):
        if self.editable:
            self.editing=True
        if self.on_double_press:
            self.on_double_press()

    def handle_edit_confirm(self, text):
        assert self.editing
        self.text = text
        if self.on_change:
            self.on_change()

    def build(self):
        return rio.SimpleTreeItem(
            content = self.build_content(),
            children = [child.build() for child in self.children],
            is_expanded = self.is_expanded,
            on_press=self.on_press,
        )

class RioTreeItem(RioTreeItemBase):
    def __init__(self, *children,text='',**kwargs):
        super().__init__(children=list(children),key=text,text=text,**kwargs)

class TreeItem(Widget, i.TreeItem):
    __slots__ = ('handlers',)
    s_component_class = RioTreeItem

    def __init__(self, parent: TreeWidget|TreeItem, *args, **kwargs ):
        super().__init__(*args,**kwargs)
        parent['children'] = parent['children'] + [self]
        self.handlers = parent.handlers
        for name, callback in self.handlers.items():
            self[name.replace('_item_', '_')] = partial(callback, self)

    def child_count(self):
        return len(self['children'])

    def set_expanded(self, expanded: bool):
        self['is_expanded'] = expanded

    def set_text(self, col: int, text: str):
        self['text'] = text

    def set_tool_tip(self, col: int, tooltip: str):
        self['tooltip'] = tooltip

class RioTreeView(rio.Component):
    """makes item-level callbacks available on the tree level"""
    children: list[DynamicComponent]
    _=KW_ONLY
    selection_mode: Literal["none", "single", "multiple"] = "none",
    col_count: int = 1
    header_labels: list[str] = ['header']


    def __init__(self,*children,
            selection_mode: Literal["none", "single", "multiple"]='none',
            col_count: int = 1,
            header_labels: list[str] = None,
            **kwargs
        ):
        super().__init__(**kwargs)
        self.children=list(children)
        self.selection_mode=selection_mode
        self.col_count=col_count
        if header_labels:
            self.header_labels=header_labels

    def build(self):
        return rio.TreeView(
            *[item.build() for item in self.children],
            selection_mode = self.selection_mode
        )

class TreeWidget(Widget, i.TreeWidget):
    __slots__ = ('handlers',)
    s_component_class = RioTreeView
    s_default_kwargs = dict(selection_mode='single')

    def __init__(self, *args, **kwargs):
        super().__init__(*args,**kwargs)
        self.handlers = {}

    def set_column_count(self, col_count: int):
        """Set the number of columns in the tree widget."""
        assert col_count in [1,2], 'col_count must be 1 or 2'
        self['col_count'] = col_count

    def set_header_labels(self, labels: list):
        """Set the header labels for each column."""
        self['header_labels'] = labels

    def top_level_item_count(self) -> int:
        """Return the number of top-level items."""
        return len(self['children'])

    def top_level_item(self, i: int) -> TreeItem:
        """Return the top-level item at index i."""
        return self['children'][i]

    def resize_column_to_contents(self, col: int):
        """Adjust the width of the specified column (placeholder)."""
        pass

    def item_expanded_connect(self, bound_method):
        self.handlers['on_item_expand'] = self.callback(bound_method)

    def item_clicked_connect(self, bound_method):
        #self.handlers['on_item_double_press'] = bound_method
        self.handlers['on_item_press'] = self.callback(bound_method)


    def item_pressed_connect(self, bound_method):
        self.handlers['on_item_press'] = bound_method

    def item_changed_connect(self, bound_method):
        raise NotImplementedError

    def edit_item(self, item: TreeItem, col: int):
        """Start editing the specified item in the given column (placeholder)."""
        #self.component.start_editing(item, col)
        raise NotImplementedError

    def open_persistent_editor(self, item: TreeItem, col: int):
        """Open a persistent editor for the specified item and column (placeholder)."""
        #self.component.open_persistent_editor(item, col)
        raise NotImplementedError

    def add_top_level_item(self, item: TreeItem):
        """Add a top-level item to the tree (helper method)."""
        self['children'].append(item)


class CalendarWidget(Widget,i.CalendarWidget):
    s_component_class = rio.Calendar
    s_default_kwargs = dict( value = date.today() )
    s_children_attr = 'value'
    s_single_child = True

    def set_grid_visible(self, grid_visible: bool):
        pass

    def set_selected_date(self, selected_date: date):
        self['value'] = selected_date

    def selected_date(self) -> date:
        if self.component:
            return self.component._build_data_.build_result.value
        return self['value']

