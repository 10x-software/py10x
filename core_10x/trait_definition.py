from __future__ import annotations

import copy
from collections import defaultdict

from core_10x_i import BFlags, BTraitFlags
from typing_extensions import Never

from core_10x.ui_hint import Ui, UiHintModification
from core_10x.xnone import XNone, XNoneType

# fmt: off
#---- Attribute Tags
NAME_TAG        = 'name'
DATATYPE_TAG    = 'data_type'
FLAGS_TAG       = 'flags'
DEFAULT_TAG     = 'default'
FORMAT_TAG      = 'fmt'
PARAMS_TAG      = 'params'
GETTER_PARAMS_TAG = 'getter_params'
UI_HINT_TAG     = 'ui_hint'
# fmt: on


class TraitDefinition:
    # fmt: off
    __slots__ = (
        NAME_TAG,
        DATATYPE_TAG,
        FLAGS_TAG,
        DEFAULT_TAG,
        FORMAT_TAG,
        PARAMS_TAG,
        UI_HINT_TAG,
    )

    s_known_attributes = {
        DATATYPE_TAG:   lambda: XNoneType,
        FLAGS_TAG:      lambda: BFlags(0x0),
        DEFAULT_TAG:    lambda: XNone,
        FORMAT_TAG:     lambda: '',
        UI_HINT_TAG:    lambda: Ui(),
    }
    # fmt: on

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

    def __floordiv__(self, comment):
        """Add or replace comment in params with // operator"""
        assert isinstance(comment, str), f'Trait comment must be a string: {comment}'
        ui_hint = getattr(self, UI_HINT_TAG)
        ui_hint.tip = comment
        return self

    def __call__(self, *args, **kwargs):
        """Prevent IDE from complaining about calling traits with parameters"""
        ...

    def set_widget_type(self, widget_type: Ui.WIDGET_TYPE):
        ui_hint = getattr(self, UI_HINT_TAG)
        ui_hint.widget_type = widget_type

    def copy(self) -> TraitDefinition:
        return copy.deepcopy(self)

    def flags_change(self, flags_value):
        dt = type(flags_value)
        if dt is tuple:
            assert len(flags_value) == 2, f'Changing {self.name} flags expects (flags_to_set, flags_to_reset)'
            flags_to_set, flags_to_reset = flags_value
            self.flags.set_reset(0 if flags_to_set is None else flags_to_set.value(), flags_to_reset.value())
        else:
            self.flags.set(flags_value.value())

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
        already_processed = defaultdict(bool)

        n = len(the_args)
        while n:
            arg = the_args.pop(0)
            dt = type(arg)
            if dt is Ui:  # -- only Ui hint is given, no more args
                assert not already_processed[UI_HINT_TAG], f'Duplicated Ui hint: {args}'
                assert n == 1, f'No positional args after Ui hint: {args}'
                kwargs[UI_HINT_TAG] = arg
                already_processed[UI_HINT_TAG] = True

            elif issubclass(dt, BFlags):  # -- no default value => n <=2
                assert not already_processed[FLAGS_TAG], f'Duplicated T.flags: {args}'
                assert n <= 2, f'Too many positional args after T.flags: {args}'
                kwargs[FLAGS_TAG] = arg
                already_processed[FLAGS_TAG] = True

            else:  # -- must be a default value
                assert not already_processed[DEFAULT_TAG], f'Duplicated default value: {args}'
                kwargs[DEFAULT_TAG] = arg
                already_processed[DEFAULT_TAG] = True

            n -= 1


class TraitModification(TraitDefinition):
    # fmt: off
    s_known_attributes = {
        FLAGS_TAG:      lambda: Never,
        DEFAULT_TAG:    lambda: Never,
        FORMAT_TAG:     lambda: Never,
        UI_HINT_TAG:    UiHintModification
    }

    s_modifiers = {
        FLAGS_TAG:      lambda self, flags_modification: self.flags_change(flags_modification),
        UI_HINT_TAG:    lambda self, ui_hint_modification: ui_hint_modification.apply(self)
    }
    # fmt: on
    def apply(self, trait_def: TraitDefinition) -> TraitDefinition:
        res = trait_def.copy()
        modifiers = self.__class__.s_modifiers
        for attr_name in self.__class__.s_known_attributes:
            modified_value = getattr(self, attr_name)
            if modified_value is not Never:
                modifier = modifiers.get(attr_name)
                if modifier:
                    modifier(res, modified_value)
                else:
                    setattr(res, attr_name, modified_value)
        res.params.update(self.params)
        getattr(self, UI_HINT_TAG).apply(getattr(trait_def, UI_HINT_TAG))
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


def RT(*args, **kwargs) -> TraitDefinition:  # noqa: N802
    trait_def = TraitDefinition(*args, **kwargs)
    trait_def.flags.set(T.RUNTIME.value())
    return trait_def


def M(*args, **kwargs) -> TraitModification:  # noqa: N802
    return TraitModification(*args, **kwargs)
