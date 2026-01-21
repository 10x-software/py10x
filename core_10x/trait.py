from __future__ import annotations

import ast
import copy
import functools
import inspect
import locale
import platform
import sys
from inspect import Parameter
from types import GenericAlias
from typing import get_origin, get_type_hints

from core_10x_i import BTrait

from core_10x.named_constant import NamedConstant
from core_10x.rc import RC
from core_10x.trait_definition import T, TraitDefinition, Ui
from core_10x.xnone import XNone


class Trait(BTrait):
    # TODO: re-enable __slots__ when the dust settles..
    # __slots__ = ('t_def','getter_params')
    s_datatype_traitclass_map = {}

    @staticmethod
    def register_by_datatype(trait_class, data_type):
        assert inspect.isclass(trait_class) and issubclass(trait_class, Trait), 'trait class must be a subclass of Trait'
        found = Trait.s_datatype_traitclass_map.get(data_type)
        assert not found, f'data_type {data_type} for {trait_class} is already registered for {found}'
        Trait.s_datatype_traitclass_map[data_type] = trait_class

    s_baseclass_traitclass_map = {}

    @staticmethod
    def register_by_baseclass(trait_class, base_class):
        assert inspect.isclass(trait_class) and issubclass(trait_class, Trait), 'trait class must be a subclass of Trait'
        assert inspect.isclass(base_class), 'base class must be a class'
        found = Trait.s_baseclass_traitclass_map.get(base_class)
        assert not found, f'base_class {base_class} for {trait_class} is already registered for {found}'
        Trait.s_baseclass_traitclass_map[base_class] = trait_class

    @staticmethod
    def real_trait_class(data_type):
        real_trait_class = Trait.s_datatype_traitclass_map.get(data_type)
        if real_trait_class:
            return real_trait_class

        tmap = Trait.s_baseclass_traitclass_map
        base_class: type
        for base_class in reversed(tmap):
            if issubclass(data_type, base_class):
                return tmap[base_class]

        return generic_trait

    s_ui_hint = None

    def __init_subclass__(cls, data_type: type = None, register: bool = True, base_class: type = False):
        cls.s_baseclass = base_class
        if register:
            assert data_type and inspect.isclass(data_type), f'{cls} - data_type is not valid'
            if base_class:
                Trait.register_by_baseclass(cls, data_type)
            else:
                Trait.register_by_datatype(cls, data_type)

        assert cls.s_ui_hint, f'{cls} must define s_ui_hint'

    def __init__(self, t_def: TraitDefinition, btrait: BTrait = None):
        if btrait is None:
            super().__init__()
        else:
            super().__init__(btrait)

        self.t_def = t_def
        self.getter_params = ()

    def __get__(self, instance, owner):
        if not self.getter_params:
            return instance.get_value(self)

        return functools.partial(instance.get_value, self)

    def __set__(self, instance, value):
        if not self.getter_params:
            instance.set_value(self, value).throw()

        else:
            if not isinstance(value, trait_value):
                raise TypeError(f'May not set a value to {instance.__class__.__name__}.{self.name} as it requires params')

            instance.set_value(self, value.value, *value.args).throw()

    # def __deepcopy__(self, memodict={}):
    #    return Trait(self.t_def.copy(), btrait = self)

    @staticmethod
    def create(trait_name: str, t_def: TraitDefinition) -> Trait:
        dt = t_def.data_type
        if isinstance(dt, GenericAlias):
            dt = get_origin(dt)  # get original type, e.g. `list` from `list[int]`
            # TODO: could be useful to also keep get_args(dt) for extra checking?
        trait_class = Trait.real_trait_class(dt)
        trait = trait_class(t_def)
        trait.set_name(trait_name)
        trait.data_type = dt
        trait.flags = t_def.flags.value()
        trait.default = t_def.default
        if t_def.fmt:
            trait.fmt = t_def.fmt

        trait.create_proc()

        trait.post_ctor()
        ui_hint: Ui = copy.deepcopy(t_def.ui_hint)
        ui_hint.adjust(trait)
        trait.ui_hint = ui_hint
        return trait

    @staticmethod
    def method_defs(trait_name: str) -> dict:
        return {
            f'{trait_name}_{(method_suffix := method_key.lower())}': (method_suffix, method_def)
            for method_key, method_def in TRAIT_METHOD.s_dir.items()
        }

    def set_trait_funcs(self, traitable_cls, rc):
        for method_name, (method_suffix, method_def) in Trait.method_defs(self.name).items():
            method = getattr(traitable_cls, method_name, None)
            if method and method_suffix == 'get' and self.t_def.default is not XNone:  # -- getter and default are defined - figure out which to use
                for cls in traitable_cls.__mro__:
                    cls_vars = vars(cls)
                    if method_name in cls_vars:  # -- found method on cls - use method, unless
                        if isinstance(cls_vars.get(self.name), TraitDefinition):  # -- default is on same cls then - error
                            rc.add_error(
                                f'Ambiguous definition for {method_name} on {cls} - both trait.default and traitable.{method_name} are defined.'
                            )
                    elif isinstance(cls_vars.get(self.name), TraitDefinition):  # -- default found on cls - use default
                        method = None  # use default
                    else:
                        continue
                    break

            f = method_def.value(self, method, method_suffix, rc)
            if f:
                set_f = getattr(self, f'set_f_{method_suffix}')
                set_f(f, bool(method))

    def create_f_get(self, f, attr_name: str, rc: RC):
        if not f:  # -- no custom getter, just the default value
            f = lambda traitable: self.default_value()
            f.__name__ = 'default_value'
            params = ()

        else:
            # TODO: if default is defined in a subclass relative to where the getter is defined, override the getter?

            sig = inspect.signature(f)
            params = []
            param: Parameter
            for pname, param in sig.parameters.items():
                if pname != 'self':
                    pkind = param.kind
                    if pkind != Parameter.POSITIONAL_OR_KEYWORD:
                        rc.add_error(f'{f.__name__} - {pname} is not a positional parameter')
                    else:
                        params.append(param)
            params = tuple(params)

        self.getter_params = params
        return f

    def create_f_set(self, f, attr_name: str, rc: RC):
        if not f:
            return None

        # -- custom setter
        resolved_hints = get_type_hints(f, sys.modules[f.__module__].__dict__ if f.__module__ in sys.modules else {}, f.__class__.__dict__)
        assert resolved_hints.get('return') is RC, f'{f.__name__} - setter must return RC'

        sig = inspect.signature(f)
        params = tuple(sig.parameters.values())
        n = len(params)
        if n < 3:
            rc.add_error(f'{f.__name__} - setter must have at least 3 parameters: self, trait, value')

        getter_params = self.getter_params
        if getter_params:
            if getter_params != tuple(params[3:]):
                rc.add_error(f'{f.__name__} - setter must have same params as the getter: {getter_params}')

        return f

    def create_f_common_trait_with_value(self, f, attr_name: str, rc: RC):
        cls = self.__class__
        # TODO: check f's signature
        if not f:
            common_f = getattr(cls, attr_name, None)
            if common_f:
                f = lambda obj_or_cls, trait, value: common_f(trait, value)
                f.__name__ = f'{cls.__name__}.{common_f.__name__}'

        return f

    def create_f_common_trait_with_value_static(self, f, attr_name: str, rc: RC):
        cls = self.__class__
        if f:
            assert isinstance(f.__self__, type), f'{f.__name__} must be declared as @classmethod'
        else:
            f = getattr(cls, attr_name, None)
        return self.create_f_common_trait_with_value(f, attr_name, rc)

    def create_f_choices(self, f, attr_name: str, rc: RC):
        cls = self.__class__
        if not f:
            choices_f = getattr(cls, attr_name, None)
            if choices_f:
                f = lambda obj, trait: choices_f(trait)
                f.__name__ = f'{cls.__name__}.{choices_f.__name__}'

        return f

    def create_f_plain(self, f, attr_name: str, rc: RC):
        return f

    # =======================================================================================================================
    #   Formatting
    # =======================================================================================================================
    # fmt: off
    s_locales = {
        'Windows':      'USA',
        'Linux':        'en_US',
    }
    # fmt: on

    def locale_change(self, old_value, value):
        if value:
            return value

        try:
            return locale.setlocale(locale.LC_NUMERIC, self.__class__.s_locales.get(platform.system(), 'en_US'))
        except Exception:
            return None

    def _format(self, fmt: str) -> str:
        if not fmt:
            fmt = ':'
        else:
            c = fmt[0]
            if c != '!' and c != ':':
                fmt = ':' + fmt

        return f'{{{fmt}}}'

    def use_format_str(self, fmt: str, value) -> str:
        if isinstance(value, str) and not fmt:
            return value
        return self._format(fmt).format(value)

    # ===================================================================================================================
    #   Trait Interface
    # ===================================================================================================================

    def post_ctor(self): ...

    def check_integrity(self, cls, rc: RC):
        pass

    def default_value(self):
        return self.default

    def same_values(self, value1, value2) -> bool:
        raise NotImplementedError

    def from_any(self, value):
        if isinstance(value, self.data_type):
            return value

        if isinstance(value, str):
            return self.from_str(value)

        return self.from_any_xstr(value)

    def from_str(self, s: str):
        lit = ast.literal_eval(s)
        return self.from_any_xstr(lit)

    def from_any_xstr(self, value):
        raise NotImplementedError

    def to_str(self, v) -> str:
        return self.use_format_str(self.fmt, v)

    def is_acceptable_type(self, data_type: type) -> bool:
        return data_type is self.data_type

    def serialize(self, value):
        raise NotImplementedError

    def deserialize(self, value) -> RC:
        raise NotImplementedError

    def to_id(self, value) -> str:
        raise NotImplementedError

    def choices(self):
        return XNone

    # TODO: unify XNone/None conversions with object serialization/deserializatoin in c++
    # TODO: call these from c++ directly in place of f_serialize/f_deserialize?
    def serialize_value(self, value, replace_xnone=False):
        value = self.f_serialize(self, value)
        return None if replace_xnone and value is XNone else value

    def deserialize_value(self, value, replace_none=False):
        value = self.f_deserialize(self, value)
        return XNone if replace_none and value is None else value

    # ===================================================================================================================


# ---- Methods Associated with a trait
# fmt: off
class TRAIT_METHOD(NamedConstant):
    GET                 = Trait.create_f_get
    SET                 = Trait.create_f_set
    VERIFY              = Trait.create_f_plain
    FROM_STR            = Trait.create_f_common_trait_with_value
    FROM_ANY_XSTR       = Trait.create_f_common_trait_with_value
    IS_ACCEPTABLE_TYPE  = Trait.create_f_common_trait_with_value
    TO_STR              = Trait.create_f_common_trait_with_value
    SERIALIZE           = Trait.create_f_common_trait_with_value_static
    DESERIALIZE         = Trait.create_f_common_trait_with_value_static
    TO_ID               = Trait.create_f_common_trait_with_value
    CHOICES             = Trait.create_f_choices
    STYLE_SHEET         = Trait.create_f_plain
# fmt: on


class generic_trait(Trait, register=False):
    s_ui_hint = Ui.NONE

    def post_ctor(self):
        assert not self.flags_on(T.ID), f'generic trait {self.name} may not be an ID trait'
        assert self.flags_on(T.RUNTIME), f'generic trait {self.name} must be a RUNTIME trait'

    def is_acceptable_type(self, data_type: type) -> bool:
        return issubclass(data_type, self.data_type)

    def same_values(self, value1, value2) -> bool:
        return value1 is value2


class trait_value:
    def __init__(self, value, *args):
        self.value = value
        self.args = args

    def __call__(self, *args, **kwargs): ...


class BoundTrait:
    def __init__(self, obj, trait: Trait):
        self.obj = obj
        self.trait = trait
        # self.args = ()

    def __getattr__(self, attr_name):
        trait_attr = getattr(self.trait, attr_name, None)
        if trait_attr:
            # if callable(trait_attr):
            return trait_attr

        return lambda: getattr(self.obj, attr_name)(self.trait)

    def __call__(self):
        return self.trait
