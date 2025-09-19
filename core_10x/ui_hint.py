import copy
import functools

from core_10x_i import BTraitFlags as T

from core_10x.named_constant import Enum


class UiHint:
    # fmt: off
    #-- Flags
    HIDDEN      = 0x1
    READ_ONLY   = 0x2
    SELECT_ONLY = 0x4
    SEPARATOR   = 0x8

    #-- Stylesheet Attributes
    FG_COLOR        = 'color'
    BG_COLOR        = 'background-color'
    FONT            = 'font-family'
    FONT_STYLE      = 'font-style'
    FONT_WEIGHT     = 'font-weight'
    BORDER_WEIGHT   = 'border-weight'
    BORDER_WIDTH    = 'border-width'
    BORDER_COLOR    = 'border-color'
    BORDER_STYLE    = 'border-style'

    class WIDGET_TYPE(Enum):  # noqa: N801
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
    # fmt: on
    @staticmethod
    def partial(widget_type_fn, **params):
        return functools.partial(widget_type_fn, **params)

    def __init__(self, label: str = None, flags: int = 0x0, tip: str = None, widget_type: WIDGET_TYPE = None, **params):
        self.label: str = label
        self.flags: int = flags
        self.tip: str = tip
        self.widget_type = widget_type
        self.params: dict = params

    def adjust(self, trait):
        if self.label is None:
            self.label = ' '.join(p.capitalize() for p in trait.name.split('_'))

        if self.tip is None:
            self.tip = self.label

        if self.widget_type is None:
            self.widget_type = trait.s_ui_hint.widget_type

        trait_flags = trait.flags
        if trait_flags & T.HIDDEN.value():
            self.flags |= self.HIDDEN
        if trait_flags & T.READONLY.value():
            self.flags |= self.READ_ONLY

    def flags_on(self, flags: int) -> bool:
        return bool(self.flags & flags)

    def set_reset_flags(self, to_set: int, to_reset: int = 0x0):
        self.flags = (self.flags | to_set) & ~to_reset

    def param(self, param_name: str, default_value):
        return self.params.get(param_name, default_value)

    @staticmethod
    def line(label: str = None, flags: int = 0x0, tip: str = None, min_width: int = 1, align_h: int = 1):
        return Ui(label=label, flags=flags, tip=tip, widget_type=Ui.WIDGET_TYPE.LINE, min_width=min_width, align_h=align_h)

    @staticmethod
    def text(label: str = None, flags: int = 0x0, tip: str = None, min_width: int = 1):
        return Ui(label=label, flags=flags, tip=tip, widget_type=Ui.WIDGET_TYPE.TEXT, min_width=min_width)

    @staticmethod
    def text4list(label: str = None, flags: int = 0x0, tip: str = None, min_width: int = 1):
        return Ui(label=label, flags=flags, tip=tip, widget_type=Ui.WIDGET_TYPE.TEXT4LIST, min_width=min_width)

    @staticmethod
    def password(label: str = None, flags: int = 0x0, tip: str = None, min_width: int = 10):
        return Ui(label=label, flags=flags, tip=tip, widget_type=Ui.WIDGET_TYPE.PASSWORD, min_width=min_width)

    @staticmethod
    def check(label: str = None, flags: int = 0x0, tip: str = None, right_label: bool = False, align_h: int = 1):
        return Ui(label=label, flags=flags, tip=tip, widget_type=Ui.WIDGET_TYPE.CHECK, right_label=right_label, align_h=align_h)

    @staticmethod
    def choice(label: str = None, flags: int = 0x0, tip: str = None, align_h: int = 1):
        return Ui(label=label, flags=flags, tip=tip, widget_type=Ui.WIDGET_TYPE.CHOICE, align_h=align_h)

    @staticmethod
    def pixmap(label: str = None, flags: int = 0x0, tip: str = None, w: int = 10, h: int = 10):
        return Ui(label=label, flags=flags, tip=tip, widget_type=Ui.WIDGET_TYPE.PIXMAP, w=w, h=h)

    @staticmethod
    def button(label: str = None, flags: int = 0x0, tip: str = None, min_width: int = 1):
        return Ui(label=label, flags=flags, tip=tip, widget_type=Ui.WIDGET_TYPE.PUSH, min_width=min_width)

    @staticmethod
    def file(label: str = None, flags: int = 0x0, tip: str = None, min_width: int = 1):
        return Ui(label=label, flags=flags, tip=tip, widget_type=Ui.WIDGET_TYPE.FILE, min_width=min_width)


class UiHintModification(UiHint):
    # fmt: off
    def __init__(
        self,
        label: str                      = None,
        flags: int                      = None,
        tip: str                        = None,
        widget_type: UiHint.WIDGET_TYPE = None,
        **params,
    ):
        # fmt: on
        super().__init__(label, flags = flags, tip = tip, widget_type = widget_type, **params)

    def apply(self, ui_hint: UiHint) -> UiHint:
        hint = copy.deepcopy(ui_hint)
        if self.label is not None:
            hint.label = self.label

        flags = self.flags
        if flags is not None:
            if isinstance(flags, int):      #-- to_set
                hint.flags |= flags
            elif isinstance(flags, tuple):  #-- (to_set, to_reset)
                hint.flags = (hint.flags | flags[0]) & ~flags[1]

        if self.tip is not None:
            hint.tip = self.tip

        if self.widget_type is not None:
            hint.widget_type = self.widget_type

        hint.params.update(self.params)

        return hint


# fmt: off
UiHint.NONE = UiHint(widget_type = UiHint.WIDGET_TYPE.NONE)
Ui          = UiHint
UiMod       = UiHintModification
# fmt: on
