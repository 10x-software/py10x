from __future__ import annotations

import inspect
from contextlib import contextmanager
from dataclasses import dataclass

from core_10x.named_constant import Enum, NamedConstant
from core_10x.rc import RC
from core_10x.ts_store import TsStore

import rio
import ui_10x.platform_interface as i
from ui_10x.rio.style_sheet import StyleSheet


@dataclass
class UserSessionContext:
    #TODO: backbone
    host: str
    dbname: str
    traitable_store: TsStore = None
    authenticated: bool = False


CURRENT_SESSION: rio.Session | None = None
@contextmanager
def session_context(session: rio.Session):
    global CURRENT_SESSION
    assert CURRENT_SESSION is None, "Must exit from session context first! Are you using async calls in session context?"
    CURRENT_SESSION = session
    try:
        traitable_store = session[UserSessionContext].traitable_store
    except Exception:
        traitable_store = None
    if traitable_store:
        traitable_store.begin_using()
    try:
        yield
    finally:
        if traitable_store:
            traitable_store.end_using()
        CURRENT_SESSION = None

class FontMetrics(i.FontMetrics):
    __slots__ = ('_widget',)
    def __init__(self, w: Widget):
        self._widget = w

    def average_char_width(self) -> int:
        return 1 # best guess -- rio measures sizes in char heights

class SizePolicy(Enum):
    MINIMUM_EXPANDING = ()
    PREFERRED = ()

class TEXT_ALIGN(NamedConstant): # noqa: N801
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


class DynamicComponent(rio.Component):
    builder: ComponentBuilder|None = None
    revision: int = 0

    def __post_init__(self):
        self.key = f'dc_{id(self.builder)}'

    def build(self) -> rio.Component:
        _=self.revision
        component = self.builder.build(self.session)
        return component


class ComponentBuilder:
    __slots__ = ('_kwargs', 'component', 'subcomponent')

    s_component_class : type[rio.Component] = None
    s_forced_kwargs = {}
    s_default_kwargs = {}
    s_dynamic = True
    s_children_attr = 'children'
    s_single_child = False
    s_size_adjustments = ('min_width', 'min_height', 'margin_left', 'margin_top', 'margin_right', 'margin_bottom','margin_x', 'margin_y', 'margin')
    s_layout_attrs = ('grow_x', 'grow_y', 'align_x', 'align_y')

    @staticmethod
    def current_session():
        return CURRENT_SESSION

    def _get_children(self) -> list:
        children = self.get_children()
        if self.s_single_child and children is None:
            return []
        return [children] if self.s_single_child else children

    def get_children(self):
        return self[self.s_children_attr]

    def set_children(self,children):
        self[self.s_children_attr] = children
        self.force_update()

    def child_count(self):
        return len(self.get_children())

    def _set_children(self,children):
        if self.s_single_child and not children:
            self.set_children(None)
        else:
            assert not self.s_single_child or len(children) == 1
            self.set_children(children[0] if self.s_single_child else children)

    def _make_kwargs(self,**kwargs):
        defaults = {
            kw: value(self, kwargs) if callable(value) else value
            for kw, value in self.s_default_kwargs.items()
        }
        return defaults | kwargs | self.s_forced_kwargs | dict(key=id(self))

    def __init__(self, *children, **kwargs):
        assert self.s_component_class, f"{self.__class__.__name__}: has no s_component_class"
        self._kwargs = self._make_kwargs(**kwargs)
        self.component = None
        self.subcomponent = None
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
            self.get_children().extend(child for child in children if child is not None and child not in existing_children)
        self.force_update()

    def with_children(self, *args):
        if not args:
            return self
        return self.__class__(*args,**self._kwargs)

    def _build_children(self,session: rio.Session):
        return [ child(session) if isinstance(child,ComponentBuilder) else child for child in self._get_children() if child is not None]

    def build(self,session):
        kwargs = {k: v for k, v in self._kwargs.items() if k != self.s_children_attr}
        for size_adjustment in self.s_size_adjustments:
            if size_adjustment in kwargs:
                kwargs[size_adjustment] = kwargs[size_adjustment] / session.pixels_per_font_height
        children: list = self._build_children(session)
        if len(children) == 1 and isinstance(first_child := children[0], rio.Component):
            if kwargs:
                print(f'{self.__class__.__name__}.build: ignored kwargs {kwargs}')
            self.subcomponent=first_child
        elif self.s_component_class:
            self.subcomponent = self.s_component_class(*children, **kwargs)
        return self.subcomponent

    def __call__(self,session: rio.Session) -> rio.Component:
        kw = {k:self[k] for k in self.s_layout_attrs if k in self}
        self.component = DynamicComponent(builder=self,**kw) if self.s_dynamic else self.build(session)
        return self.component

    def __getitem__(self, item):
        if hasattr(self.subcomponent,item):
            return getattr(self.subcomponent,item)
        return self._kwargs[item]

    def __contains__(self,item):
        return item in self._kwargs

    @classmethod
    def _not_supported(cls,item=None):
        item = item or inspect.stack()[1].function
        print(f"{cls.__name__}.{item}: - not supported")

    def __setitem__(self, item, value):
        if item!=self.s_children_attr and not hasattr(self.s_component_class,item):
            return self._not_supported(item)
        if hasattr(self.subcomponent,item):
            setattr(self.subcomponent,item,value)
        self._kwargs[item] = value

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


class Widget(ComponentBuilder, i.Widget):
    s_component_class = rio.Container
    s_stretch_arg = 'grow_x'
    s_default_layout_factory = lambda: FlowLayout() # noqa: E731
    s_default_kwargs = dict(grow_y = False,align_y = 0)

    __slots__ = ('_layout',)

    def __init_subclass__(cls, **kwargs):
        cls.s_default_layout_factory = None
        cls.s_default_kwargs = super().s_default_kwargs | cls.s_default_kwargs

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

    def apply_style_sheet(self, style: dict) -> RC:
        if text_align := TEXT_ALIGN.from_str(style.pop("text-align", "")):
            self[text_align.rio_attr()] = text_align.rio_value()
        if hasattr(self.s_component_class,"text_style"):
            ss = StyleSheet()
            rc = ss.set_values(sheet=style)
            self["text_style"] = ss.text_style
            return rc
        return StyleSheet.rc(style)

    def set_style_sheet(self, sh: str):
        from ui_10x.utils import UxStyleSheet  #TODO: circular import
        rc = self.apply_style_sheet(UxStyleSheet.loads(sh))
        if not rc:
            print(f"{self.__class__.__name__}.set_style_sheet: \n{rc.error()}")

    def set_minimum_height(self, height: int):
        self['min_height'] = height

    def set_minimum_width(self, width: int):
        self['min_width'] = width

    def set_size_policy(self, x_policy: SizePolicy, y_policy: SizePolicy):
        self['grow_x'] = x_policy == SizePolicy.MINIMUM_EXPANDING
        self['grow_y'] = y_policy == SizePolicy.MINIMUM_EXPANDING

    def set_tool_tip(self, tooltip: str):
        self['tooltip'] = tooltip

    def set_text(self, text: str):
        self["text"] = text

    def set_read_only(self, read_only: bool):
        self['is_sensitive'] = not read_only

    def style_sheet(self) -> str:
        ##TODO
        self._not_supported()
        return ""

    def set_enabled(self, enabled: bool):
        self['is_sensitive'] = enabled

    def font_metrics(self) -> FontMetrics:
        return FontMetrics(self)

    def set_geometry(self, *args):
        ##TODO
        self._not_supported()

    def width(self) -> int:
        ##TODO
        self._not_supported()
        return 0

    def height(self) -> int:
        ##TODO
        self._not_supported()
        return 0

    def map_to_global(self, point: Point) -> Point:
        ##TODO
        self._not_supported()
        return point


class Layout(Widget, i.Layout):
    def add_widget(self, widget: Widget, stretch=None, **kwargs):
        assert not kwargs, f'kwargs not supported: {kwargs}'
        assert widget is not None
        if stretch is not None:
            widget.set_stretch(stretch)
        self.get_children().append(widget)

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


class FlowLayout(Layout, i.Layout):
    s_component_class = rio.FlowContainer


@dataclass
class Point(i.Point):
    _x: int = 0
    _y: int = 0

    def x(self) -> int:
        return self._x

    def y(self) -> int:
        return self._y