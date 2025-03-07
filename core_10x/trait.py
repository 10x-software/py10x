import ast
import functools
import locale
import platform
import inspect
import functools
from inspect import Parameter
import copy

from core_10x_i import BTrait

from core_10x.xnone import XNone
from core_10x.named_constant import NamedConstant
from core_10x.trait_definition import TraitDefinition, T, Ui
from core_10x.rc import RC


class Trait(BTrait):
    #TODO: re-enable __slots__ when the dust settles..
    #__slots__ = ('t_def','getter_params')
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

        map = Trait.s_baseclass_traitclass_map
        base_class: type
        for base_class in reversed(map):
            if issubclass(data_type, base_class):
                return map[base_class]

        return generic_trait

    s_ui_hint = None
    def __init_subclass__(cls, data_type = None, register = True, base_class = False):
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

    #def __deepcopy__(self, memodict={}):
    #    return Trait(self.t_def.copy(), btrait = self)

    @staticmethod
    def create(trait_name: str, t_def: TraitDefinition, class_dict: dict, annotations: dict, rc: RC) -> 'Trait':
        dt = annotations.get(trait_name) or t_def.data_type
        trait_class = Trait.real_trait_class(dt)
        trait = trait_class(t_def)
        trait.set_name(trait_name)
        trait.data_type = dt
        trait.flags = t_def.flags.value()
        trait.default = t_def.default
        if t_def.fmt:
            trait.fmt = t_def.fmt

        trait.create_proc()
        Trait.set_trait_funcs(class_dict, rc, trait, trait_name)

        trait.post_ctor()
        ui_hint: Ui = copy.deepcopy(t_def.ui_hint)
        ui_hint.adjust(trait)
        trait.ui_hint = ui_hint
        return trait

    @staticmethod
    def method_defs(trait_name: str) -> dict:
        return {f'{trait_name}_{(method_suffix:=method_key.lower())}':(method_suffix,method_def) for method_key,method_def in TRAIT_METHOD.s_dir.items()}

    @staticmethod
    def set_trait_funcs(class_dict, rc, trait, trait_name):
        for method_name, (method_suffix,method_def) in Trait.method_defs(trait_name).items():
            method = class_dict.get(method_name)
            f = method_def.value(trait, method, method_suffix, rc)
            if f:
                cpp_name = f'set_f_{method_suffix}'
                set_f = getattr(trait, cpp_name)
                set_f(f, bool(method))

    def create_f_get(self, f, attr_name: str, rc: RC):
        if not f:  #-- no custom getter, just the default value
            f = lambda traitable: self.default_value()
            f.__name__ = 'default_value'
            params = ()

        else:
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

        #-- custom setter
        sig = inspect.signature(f)
        assert sig.return_annotation is RC, f'{f.__name__} - setter must return RC'
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
        if not f:
            common_f = getattr(cls, attr_name, None)
            if common_f:
                f = lambda obj, trait, value: common_f(trait, value)
                f.__name__ = f'{cls.__name__}.{common_f.__name__}'

        return f

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

#=======================================================================================================================
#   Formatting
#=======================================================================================================================
    s_locales = {
        'Windows':      'USA',
        'Linux':        'en_US',
    }
    def locale_change(self, old_value, value):
        if value:
            return value

        try:
            return locale.setlocale(locale.LC_NUMERIC, self.__class_.s_locales.get(platform.system(), 'en_US'))
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

    #===================================================================================================================
    #   Trait Interface
    #===================================================================================================================

    def post_ctor(self):
        ...

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

    #===================================================================================================================

#---- Methods Associated with a trait
class TRAIT_METHOD(NamedConstant):
    GET             = Trait.create_f_get
    SET             = Trait.create_f_set
    VERIFY          = Trait.create_f_plain
    FROM_STR        = Trait.create_f_common_trait_with_value
    FROM_ANY_XSTR   = Trait.create_f_common_trait_with_value
    TO_STR          = Trait.create_f_common_trait_with_value
    SERIALIZE       = Trait.create_f_common_trait_with_value
    DESERIALIZE     = Trait.create_f_common_trait_with_value
    TO_ID           = Trait.create_f_common_trait_with_value
    CHOICES         = Trait.create_f_choices
    STYLE_SHEET     = Trait.create_f_plain


class generic_trait(Trait, register = False):
    s_ui_hint = Ui.NONE

    def post_ctor(self):
        assert not self.flags_on(T.ID), f"generic trait {self.name} may not be an ID trait"
        assert self.flags_on(T.RUNTIME), f"generic trait {self.name} must be a RUNTIME trait"

    def is_acceptable_type(self, data_type: type) -> bool:
        return issubclass(data_type, self.data_type)

    def same_values(self, value1, value2) -> bool:
        return value1 is value2

class trait_value:
    def __init__(self, value, *args):
        self.value = value
        self.args = args

    def __call__(self, *args, **kwargs):
        ...

class BoundTrait:
    def __init__(self, obj, trait: Trait):
        self.obj = obj
        self.trait = trait
        #self.args = ()

    def __getattr__(self, attr_name):
        trait_attr = getattr(self.trait, attr_name)
        #if callable(trait_attr):
        return trait_attr

    def __call__(self):
        return self.trait

class TraitMethodError(Exception):
    """
    NOTE: other_exc must be set in except clause ONLY!
    """
    @staticmethod
    def create(
        traitable,
        trait: Trait,
        method_name: str,
        reason: str             = '',
        value                   = XNone,
        args: tuple             = (),
        other_exc: Exception    = None
    ):
        if isinstance(other_exc, TraitMethodError):
            return other_exc

        msg = []
        msg.append(f'Failed in {traitable.__class__.__name__}.{trait.name}.{method_name}')
        msg.append(f'    object = {traitable.id()};')

        if reason:
            msg.append(f'    reason = {reason}')

        if value is not None:
            msg.append(f'    value = {value}')

        if args:
            msg.append(f'    args = {args}')

        if other_exc:
            msg.append(f'original exception = {str(other_exc)}')

        return TraitMethodError('\n'.join(msg))



