import copy

from core_10x_i import BTraitFlags, BFlags

from core_10x.xnone import XNone
from core_10x.ui_hint import Ui

#---- Attribute Tags
NAME_TAG        = 'name'
DATATYPE_TAG    = 'data_type'
FLAGS_TAG       = 'flags'
DEFAULT_TAG     = 'default'
FORMAT_TAG      = 'fmt'
PARAMS_TAG      = 'params'
GETTER_PARAMS_TAG = 'getter_params'
UI_HINT_TAG     = 'ui_hint'

class TraitDefinition:
    __slots__ = (
        NAME_TAG,
        DATATYPE_TAG,
        FLAGS_TAG,
        DEFAULT_TAG,
        FORMAT_TAG,
        PARAMS_TAG,
        UI_HINT_TAG,
        #*tuple(cdef.value for cdef in TRAIT_METHOD.s_dir.values())
    )

    s_known_attributes = {
        FLAGS_TAG:      lambda: BFlags(0x0),
        DEFAULT_TAG:    lambda: XNone,
        FORMAT_TAG:     lambda: '',
        UI_HINT_TAG:    lambda: Ui(),
    }

    def __init__(self, *args, **kwargs):
        """
        T([default_value,] [t_flags,] [Ui(...),] **kwargs
        """
        self.process_args(args, kwargs)

        for tag, def_value_fn in self.s_known_attributes.items():
            def_value = def_value_fn()
            value = kwargs.pop(tag, def_value)
            setattr(self, tag, value)

        self.params = kwargs
        self.name = None

    def __call__(self, *args, **kwargs):    #-- to calm PyCharm down :-)
        ...

    def set_widget_type(self, widget_type: Ui.WIDGET_TYPE):
        ui_hint = getattr(self, UI_HINT_TAG)
        ui_hint.widget_type = widget_type

    def copy(self) -> 'TraitDefinition':
        return copy.deepcopy(self)

    @classmethod
    def process_args(cls, args: tuple, kwargs: dict):
        """
        args:
            optional default_value
            optional T.flags
            optional ui hint: Ui(...)
        kwargs:
            known attributes and extra params (usually empty)
        """
        the_args = list(args)
        already_processed = {
            DEFAULT_TAG:    False,
            FLAGS_TAG:      False,
            UI_HINT_TAG:    False
        }

        n = len(the_args)
        while n:
            arg = the_args.pop(0)
            dt = type(arg)
            if dt is Ui:  #-- only Ui hint is given, no more args
                assert not already_processed[UI_HINT_TAG], f'Duplicated Ui hint: {args}'
                assert n == 1, f'No positional args after Ui hint: {args}'
                kwargs[UI_HINT_TAG] = arg
                already_processed[UI_HINT_TAG] = True

            elif issubclass(dt, BFlags):  #-- no default value => n <=2
                assert not already_processed[FLAGS_TAG], f'Duplicated T.flags: {args}'
                assert n <= 2, f'Too many positional args after T.flags: {args}'
                kwargs[FLAGS_TAG] = arg
                already_processed[FLAGS_TAG] = True

            else:  #-- must be a default value
                assert not already_processed[DEFAULT_TAG], f'Duplicated default value: {args}'
                kwargs[DEFAULT_TAG] = arg
                already_processed[DEFAULT_TAG] = True

            n -= 1

class TraitModification(TraitDefinition):
    s_known_attributes = {
        FLAGS_TAG:      XNone,
        DEFAULT_TAG:    XNone,      #-- TODO: for M(..., default = XNone), the old default will NOT be changed to XNone
        FORMAT_TAG:     XNone,
    }

    def flags_change(self, flags_value):
        dt = type(flags_value)
        if dt is tuple:
            assert len(flags_value) == 2, f'Changing {self.name} flags expects (flags_to_set, flags_to_reset)'
            self.flags.set_reset(flags_value[0], flags_value[1])
        else:
            self.flags.set(flags_value)

    s_modifiers = {
        FLAGS_TAG:  lambda self, flags_modification: self.flags_change(flags_modification),
    }

    def apply(self, trait_def: TraitDefinition) -> TraitDefinition:
        res = trait_def.copy()
        modifiers = self.__class__.s_modifiers
        for attr_name in self.__class__.s_known_attributes:
            modified_value = getattr(self, attr_name)
            if modified_value is not XNone:
                modifier = modifiers.get(attr_name)
                if modifier:
                    modifier(res, modified_value)
                else:
                    setattr(res, attr_name, modified_value)

        return res

class T(BTraitFlags):
    def __new__(cls, *args, **kwargs) -> TraitDefinition:
        return TraitDefinition(*args, **kwargs)

    @staticmethod
    def fg_color(color: str) -> str:
        return f'color: {color}' if color else ''

    @staticmethod
    def bg_color(color: str) -> str:
        return f'background-color: {color}' if color else ''

    @staticmethod
    def colors(bg_color: str, fg_color: str) -> str:
        return f'background-color: {bg_color}; color: {fg_color}' if bg_color and fg_color else ''

def RT(*args, **kwargs) -> TraitDefinition:
    trait_def = TraitDefinition(*args, **kwargs)
    trait_def.flags.set(T.RUNTIME.value())
    return trait_def

def M(cls, *args, **kwargs) -> TraitModification:
    return TraitModification(*args, **kwargs)

