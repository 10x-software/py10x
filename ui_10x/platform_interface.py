import abc
from datetime import date

class Object(abc.ABC): ...

QueuedConnection            = None
AutoConnection              = None
DirectConnection            = None
UniqueConnection            = None
BlockingQueuedConnection    = None

class signal_decl(abc.ABC):
    @abc.abstractmethod
    def __init__(self, *args): ...

    @abc.abstractmethod
    def connect(self, method, type = None): ...

    @abc.abstractmethod
    def emit(self, *args): ...

class MouseEvent(abc.ABC):
    @abc.abstractmethod
    def is_left_button(self) -> bool: ...

    @abc.abstractmethod
    def is_right_button(self) -> bool: ...

class Point(abc.ABC):
    @abc.abstractmethod
    def x(self) -> int: ...

    @abc.abstractmethod
    def y(self) -> int: ...

class SizePolicy(abc.ABC):
    MinimumExpanding = None
    ...

class FontMetrics(abc.ABC):
    def average_char_width(self) -> int: ...

class Color(abc.ABC): ...

class Widget(abc.ABC):
    __slots__ = ()
    def __init__(self, *args, **kwargs) -> None: ...

    @abc.abstractmethod
    def set_layout(self, layout: 'Layout'): ...

    @abc.abstractmethod
    def set_style_sheet(self, sh: str): ...

    @abc.abstractmethod
    def style_sheet(self) -> str: ...

    @abc.abstractmethod
    def set_enabled(self, enabled: bool): ...
    #
    # @abc.abstractmethod
    # def set_geometry(self, *args): ...
    #
    # @abc.abstractmethod
    # def width(self) -> int: ...
    #
    # @abc.abstractmethod
    # def height(self) -> int: ...
    #
    # @abc.abstractmethod
    # def map_to_global(self, point: Point) -> Point: ...
    #
    # @abc.abstractmethod
    # def mouse_press_event(self, event: MouseEvent): ...
    #
    # @abc.abstractmethod
    # def focus_out_event(self, event): ...
    #
    @abc.abstractmethod
    def set_size_policy(self, *args): ...

    @abc.abstractmethod
    def set_minimum_width(self, width: int): ...

    # @abc.abstractmethod
    # def set_maximum_width(self, width: int): ...

    @abc.abstractmethod
    def set_minimum_height(self, height: int): ...

    @abc.abstractmethod
    def font_metrics(self) -> FontMetrics: ...

Horizontal  = 0
Vertical    = 1

class Layout(abc.ABC):
    def __init__(self, *args, **kwargs): ...

    @abc.abstractmethod
    def add_widget(self, widget: Widget, **kwargs): ...

    @abc.abstractmethod
    def set_spacing(self, spacing: int): ...

    @abc.abstractmethod
    def set_contents_margins(self, left, top, right, bottom): ...

class BoxLayout(Layout):
    @abc.abstractmethod
    def add_layout(self, layout: 'Layout', **kwargs): ...

class HBoxLayout(BoxLayout): ...
class VBoxLayout(BoxLayout): ...

class FormLayout(Layout):
    @abc.abstractmethod
    def add_row(self, w1: Widget, w2: Widget = None): ...

class Splitter(Widget):
    @abc.abstractmethod
    def add_widget(self, widget: Widget): ...

    @abc.abstractmethod
    def set_handle_width(self, width: int): ...

    @abc.abstractmethod
    def set_stretch_factor(self, widget_index: int, factor: int): ...

    @abc.abstractmethod
    def replace_widget(self, widget_index: int, widget: Widget): ...

class Label(Widget):
    __slots__ = ()
    @abc.abstractmethod
    def set_text(self, text: str): ...

class Style(abc.ABC):
    State_Active = None

    @abc.abstractmethod
    def standard_icon(self, style_icon): ...

class PushButton(Label):
    __slots__ = ()
    @abc.abstractmethod
    def clicked_connect(self, bound_method): ...

    @abc.abstractmethod
    def set_flat(self, flat: bool): ...

class LineEdit(Label):
    @abc.abstractmethod
    def text(self) -> str: ...

    @abc.abstractmethod
    def text_edited_connect(self, bound_method): ...

    @abc.abstractmethod
    def editing_finished_connect(self, bound_method): ...

    @abc.abstractmethod
    def set_read_only(self, readonly: bool): ...

    @abc.abstractmethod
    def set_password_mode(self): ...

    @abc.abstractmethod
    def set_tool_tip(self, tooltip: str): ...

class TextEdit(Widget):
    @abc.abstractmethod
    def to_plain_text(self) -> str: ...

    @abc.abstractmethod
    def set_plain_text(self, text: str): ...

    @abc.abstractmethod
    def set_read_only(self, readonly: bool): ...

class CheckBox(Label):
    @abc.abstractmethod
    def set_checked(self, checked: bool): ...

    @abc.abstractmethod
    def is_checked(self) -> bool: ...

    @abc.abstractmethod
    def state_changed_connect(self, bound_method): ...

class ComboBox(Widget):
 ...

class GroupBox(Widget):
    @abc.abstractmethod
    def set_title(self, title: str): ...

class RadioButton(Widget):
    __slots__ = ()
    @abc.abstractmethod
    def set_checked(self, checked: bool): ...

class ButtonGroup(Widget):
    @abc.abstractmethod
    def add_button(self, rb: RadioButton, id: int): ...

    @abc.abstractmethod
    def button(self, id: int) -> RadioButton: ...

    @abc.abstractmethod
    def checked_id(self) -> int: ...

class ListItem(abc.ABC):
    @abc.abstractmethod
    def row(self): ...

    @abc.abstractmethod
    def set_selected(self, selected: bool): ...

MatchExactly = None
class ListWidget(Widget):
    @abc.abstractmethod
    def add_item(self, item): ...

    @abc.abstractmethod
    def add_items(self, items: list): ...

    @abc.abstractmethod
    def clicked_connect(self, bound_method): ...

    @abc.abstractmethod
    def clear(self): ...

    @abc.abstractmethod
    def find_items(self, text, flags): ...

    @abc.abstractmethod
    def row(self, item: ListItem) -> int: ...

    @abc.abstractmethod
    def take_item(self, row: int): ...

class TreeItem(Widget):
    @abc.abstractmethod
    def child_count(self): ...

    @abc.abstractmethod
    def set_expanded(self, expanded: bool): ...

    @abc.abstractmethod
    def set_text(self, col: int, text: str): ...

    @abc.abstractmethod
    def set_tool_tip(self, col: int, tooltip: str): ...

class TreeWidget(Widget):
    @abc.abstractmethod
    def set_column_count(self, column_count: int): ...

    @abc.abstractmethod
    def set_header_labels(self, labels: list): ...

    @abc.abstractmethod
    def top_level_item_count(self) -> int: ...

    @abc.abstractmethod
    def top_level_item(self, i: int) -> TreeItem: ...

    @abc.abstractmethod
    def resize_column_to_contents(self, col: int): ...

    @abc.abstractmethod
    def item_expanded_connect(self, item): ...

    @abc.abstractmethod
    def item_clicked_connect(self, bound_method): ...

    @abc.abstractmethod
    def item_pressed_connect(self, bound_method): ...

    @abc.abstractmethod
    def item_changed_connect(self, bound_method): ...

    @abc.abstractmethod
    def edit_item(self, item, col: int): ...

    @abc.abstractmethod
    def open_persistent_editor(self, item, col: int): ...

class CalendarWidget(Widget):
    @abc.abstractmethod
    def set_grid_visible(self, grid_visible: bool): ...

    @abc.abstractmethod
    def set_selected_date(self, selected_date: date): ...

    @abc.abstractmethod
    def selected_date(self) -> date: ...

class Dialog(Widget):
    @abc.abstractmethod
    def set_window_title(self, title: str): ...

    @abc.abstractmethod
    def set_window_flags(self, flags):  ...

    @abc.abstractmethod
    def reject(self): ...

    @abc.abstractmethod
    def done(self, rc: int): ...

    @abc.abstractmethod
    def set_modal(self, modal: bool):   ...

    @abc.abstractmethod
    def set_geometry(self, modal: bool):   ...

    @abc.abstractmethod
    def exec(self): ...

    @abc.abstractmethod
    def show(self): ...

class MessageBox(abc.ABC):
    @classmethod
    @abc.abstractmethod
    def question(cls, parent: Widget, title: str, message: str) -> bool: ...

    @classmethod
    @abc.abstractmethod
    def warning(cls, parent: Widget, title: str, message: str): ...

    @classmethod
    @abc.abstractmethod
    def information(cls, parent: Widget, title: str, message: str): ...

    @classmethod
    @abc.abstractmethod
    def is_yes_button(cls, sb) -> bool: ...

class Application(abc.ABC):
    @classmethod
    @abc.abstractmethod
    def instance(cls) -> 'Application': ...

    @abc.abstractmethod
    def style(self): ...


class TEXT_ALIGN:
    TOP       = None
    V_CENTER  = None
    BOTTOM    = None
    LEFT      = None
    CENTER    = None
    RIGHT     = None

class SCROLL(abc.ABC):
    OFF         = None
    ON          = None
    AS_NEEDED   = None

class ScrollArea(Widget):
    @abc.abstractmethod
    def set_widget(self, w: Widget): ...

    @abc.abstractmethod
    def set_horizontal_scroll_bar_policy(self, h): ...

    @abc.abstractmethod
    def set_vertical_scroll_bar_policy(self, h): ...

class StandardItem(abc.ABC):
    @abc.abstractmethod
    def __init__(self, *args): ...

    @abc.abstractmethod
    def append_column(self, column: tuple): ...

class StandardItemModel(abc.ABC):
    @abc.abstractmethod
    def set_item(self, row: int, col: int, item: StandardItem): ...

    @abc.abstractmethod
    def column_count(self, *args) -> int: ...

    @abc.abstractmethod
    def index(self, row: int, col: int): ...

class ModelIndex(abc.ABC):
    @abc.abstractmethod
    def is_valid(self) -> bool: ...

    @abc.abstractmethod
    def child(self, row: int, col: int): ...

    @abc.abstractmethod
    def parent(self): ...

    @abc.abstractmethod
    def model(self) -> StandardItemModel: ...

    @abc.abstractmethod
    def data(self, role): ...

class AbstractTableModel(abc.ABC):
 ...

class HeaderView(abc.ABC):
    @abc.abstractmethod
    def set_model(self, model): ...

    @abc.abstractmethod
    def section_resized_connect(self, bound_method): ...

    @abc.abstractmethod
    def init_style_option(self, *args): ...

class Palette(abc.ABC):
    ButtonText  = None
    Button      = None
    Window      = None

    @abc.abstractmethod
    def set_brush(self, br_type, brush): ...


class StyleOptionHeader(abc.ABC):
    palette: Palette


ForegroundRole  = None
BackgroundRole  = None

class Separator(abc.ABC): ...

def init(style = '') -> Application:           raise NotImplementedError
def to_clipboard(text: str, **kwargs):         raise NotImplementedError
def from_clipboard(**kwargs) -> str:           raise NotImplementedError
def separator(horizontal = True) -> Separator:     raise NotImplementedError
def is_ui_thread() -> bool:                         raise NotImplementedError
