import functools
from core_10x.named_constant import Enum

class UiHint:
    HIDDEN      = 0x1
    SEPARATOR   = 0x2
    SELECT_ONLY = 0x4

    class WIDGET_TYPE(Enum):
        NONE        = ()
        LINE        = ()
        TEXT        = ()
        TEXT4LIST   = ()
        PASSWORD    = ()
        CHECK       = ()
        CHOICE      = ()
        PIXMAP      = ()
        PUSH        = ()
        FILE        = ()

    @staticmethod
    def partial(widget_type_fn, **params):
        return functools.partial(widget_type_fn, **params)

    def __init__(self, label: str, flags: int = 0x0, tip: str = '', widget_type = WIDGET_TYPE.NONE, **params):
        self.widget_type = widget_type
        self.label = label
        self.flags = flags
        self.tip = tip
        self.params = params

    def flags_on(self, flags: int) -> bool:
        return bool(self.flags & flags)

    def adjust_label(self, trait_name: str):
        if not self.label:
            self.label = self.__class__.default_label(trait_name)

    @classmethod
    def default_label(cls, snake_name: str) -> str:
        return ' '.join(p.capitalize() for p in snake_name.split('_'))

    @staticmethod
    def line(label: str, flags: int = 0x0, tip: str = '', min_width = 1):
        return Ui(label, flags = flags, tip = tip, widget_type = Ui.WIDGET_TYPE.LINE, min_width = min_width)

    @staticmethod
    def text(label: str, flags: int = 0x0, tip: str = '', min_width = 1):
        return Ui(label, flags = flags, tip = tip, widget_type = Ui.WIDGET_TYPE.TEXT, min_width = min_width)

    @staticmethod
    def text4list(label: str, flags: int = 0x0, tip: str = '', min_width = 1):
        return Ui(label, flags = flags, tip = tip, widget_type = Ui.WIDGET_TYPE.TEXT4LIST, min_width = min_width)

    @staticmethod
    def password(label: str, flags: int = 0x0, tip: str = '', min_width = 10):
        return Ui(label, flags = flags, tip = tip, widget_type = Ui.WIDGET_TYPE.PASSWORD, min_width = min_width)

    @staticmethod
    def check(label: str, flags: int = 0x0, tip: str = '', right_label = False):
        return Ui(label, flags = flags, tip = tip, widget_type = Ui.WIDGET_TYPE.CHECK, right_label = right_label)

    @staticmethod
    def choice(label: str, flags: int = 0x0, tip: str = ''):
        return Ui(label, flags = flags, tip = tip, widget_type = Ui.WIDGET_TYPE.CHOICE)

    @staticmethod
    def pixmap(label: str, flags: int = 0x0, tip: str = '', w = 10, h = 10):
        return Ui(label, flags = flags, tip = tip, widget_type = Ui.WIDGET_TYPE.PIXMAP, w = w, h = h)

    @staticmethod
    def button(label: str, flags: int = 0x0, tip: str = '', min_width = 1):
        return Ui(label, flags = flags, tip = tip, widget_type = Ui.WIDGET_TYPE.PUSH, min_width = min_width)

    @staticmethod
    def file(label: str, flags: int = 0x0, tip: str = '', min_width = 1):
        return Ui(label, flags = flags, tip = tip, widget_type = Ui.WIDGET_TYPE.FILE, min_width = min_width)


Ui = UiHint
Ui.NONE = Ui('', widget_type = Ui.WIDGET_TYPE.NONE)


