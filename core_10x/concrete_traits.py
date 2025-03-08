import ast
import inspect
import locale

from core_10x.xnone import XNone
from core_10x.nucleus import Nucleus
from core_10x.trait import Trait, T, TraitDefinition, RC
from core_10x.ui_hint import Ui
from core_10x.xdate_time import XDateTime, date, datetime
from core_10x.py_class import PyClass
from core_10x.named_constant import NamedConstant, EnumBits
from core_10x.package_refactoring import PackageRefactoring

class primitive_trait(Trait, register = False):
    s_ui_hint = Ui.NONE

    def default_value(self):
        return self.default

    def same_values(self, value1, value2) -> bool:
        return value1 == value2

    def from_str(self, s: str):
        try:
            v = ast.literal_eval(s)
            dt = self.data_type
            return v if type(v) is dt else dt(v)
        except Exception:
            return XNone

    def from_any_xstr(self, value):
        return self.data_type(value)

    # def to_str(self, v) -> str:
    #      return str(v)

    def to_id(self, v) -> str:
        return str(v)

    def serialize(self, value):
        return value

    def deserialize(self, value):
        return value


class bool_trait(primitive_trait, data_type = bool):
    s_ui_hint = Ui.check()

    fmt         = ( 'yes', '' )

    # def to_str(self, v) -> str:
    #     return str(v)

    def to_id(self, value: bool) -> str:
        return '0' if value else '1'


class int_trait(primitive_trait, data_type = int):
    s_ui_hint = Ui.line()


class float_trait(primitive_trait, data_type = float):
    s_ui_hint = Ui.line()

    fmt         = ',.2f'

    #def from_str(self, s: str) -> RC:
    #    return RC(True, locale.atof(s))

    # def to_str(self, v) -> str:
    #     return str(v)

    def is_acceptable_type(self, data_type: type) -> bool:
        return data_type is float or data_type is int


class str_trait(primitive_trait, data_type = str):
    s_ui_hint = Ui.line(align_h = -1)

    #pattern = ''
    #placeholder = ''

    def from_str(self, s: str):
        return s

    def to_str(self, v) -> str:
         return v

    def to_id(self, value: str) -> str:
        return value


# class bin_trait(Trait, data_type = bytes):
#     w = 0   #-- max width, if any and relevant
#     h = 0   #-- max height, if any and relevant
#
# def pixmap(*args, **kwargs):
#     tdef: TraitDefinition = T(bytes, *args, **kwargs)
#     tdef.set_widget_type(Ui.WIDGET_TYPE.PIXMAP)
#     return tdef

class datetime_trait(Trait, data_type = datetime):
    s_ui_hint = Ui.line(align_h = 0)

    def from_str(self, s: str):
        dt = XDateTime.str_to_datetime(s)
        if dt is None:
            raise ValueError('invalid datetime string')

        return dt

    def from_any_xstr(self, value):
        dt = XDateTime.to_datetime(value)
        if dt is None:
            raise ValueError('cannot be converted to datetime')

        return dt

    def to_str(self, v: datetime) -> str:
         return XDateTime.datetime_to_str(v)

    s_acceptable_types = { datetime, date, int, str }
    def is_acceptable_type(self, data_type: type) -> bool:
        return data_type in self.s_acceptable_types

    #-- NOTES:
    #-- 1) we believe datetime is mostly acceptable for a storage, e.g., Mongo
    #-- 2) it is in UTC, so no locale's datetime issues

    def serialize(self, value: datetime):
        return value

    def deserialize(self, value: datetime):
        return value

    def to_id(self, value) -> str:
        return XDateTime.datetime_to_str(value, with_ms = True)

class date_trait(Trait, data_type = date):
    s_ui_hint = Ui.line(min_width = 10, align_h = 0)

    def from_str(self, s: str):
        dt = XDateTime.str_to_date(s)
        if dt is None:
            raise ValueError('invalid date string')

        return dt

    def from_any_xstr(self, value):
        dt = XDateTime.to_date(value)
        if dt is None:
            raise ValueError('cannot be converted to date')

        return dt

    def to_str(self, v: datetime) -> str:
        return XDateTime.date_to_str(v)

    s_acceptable_types = { datetime, date, int, str }
    def is_acceptable_type(self, data_type: type) -> bool:
        return data_type in self.s_acceptable_types

    def serialize(self, value: date):
        return value

    def deserialize(self, value: date):
        return value

    def to_id(self, value) -> str:
        return XDateTime.date_to_str(value)

class class_trait(Trait, data_type = type):
    s_ui_hint = Ui.line(align_h = -1)

    def to_str(self, value):
        return PyClass.name(value)

    def to_id(self, value) -> str:
        return PackageRefactoring.find_class_id(value)

    def same_values(self, value1, value2) -> bool:
        return value1 is value2

    def from_str(self, s: str):
        return PackageRefactoring.find_class(s)

    def from_any_xstr(self, value):
        raise AssertionError('May not be called')

    def is_acceptable_type(self, data_type: type) -> bool:
        return inspect.isclass(data_type)

    def serialize(self, value):
        return PackageRefactoring.find_class_id(value)

    def deserialize(self, value: str):
        return PackageRefactoring.find_class(value)

class list_trait(Trait, data_type = list):
    s_ui_hint = Ui.line()

    def to_str(self, v) -> str:
        return str(v)

    def to_id(self, value) -> str:
        return str(value)

    def default_value(self) -> list:
        return list(self.default)

    def serialize(self, value: list):
        return Nucleus.serialize_list(value, self.flags_on(T.EMBEDDED))

    def deserialize(self, value: list):
        return Nucleus.deserialize_list(value)

class dict_trait(Trait, data_type = dict):
    s_ui_hint = Ui.line(flags = Ui.SELECT_ONLY)

    def use_format_str(cls, fmt: str, value) -> str:
        return str(value) if not fmt else fmt.join(f"'{key}' -> '{val}'" for key, val in value.items())

    def to_str(self, v) -> str:
        return str(v)

    def to_id(self, value) -> str:
        return str(value)

    def default_value(self) -> dict:
        return dict(self.default)

    def serialize(self, value: dict):
        return Nucleus.serialize_dict(value, self.flags_on(T.EMBEDDED))

    def deserialize(self, value: dict):
        return Nucleus.deserialize_dict(value)

class any_trait(Trait, data_type = XNone.__class__):  # -- any
    s_ui_hint = Ui.NONE

    def to_str(self, v) -> str:
        return str(v)

    def to_id(self, value) -> str:
        return str(value)

    def from_str(self, s: str):
        return None

    def from_any_xstr(self, value):
        return value

    def is_acceptable_type(self, data_type: type) -> bool:
        return True

    def serialize(self, value):
        return Nucleus.serialize_any(value, self.flags_on(T.EMBEDDED))

    def deserialize(self, value):
        return Nucleus.deserialize_any(value)

    def same_values(self, value1, value2) -> bool:
        return value1 is value2

class nucleus_trait(Trait, data_type = Nucleus, base_class = True):
    s_ui_hint = Ui.NONE

    def to_str(self, v) -> str:
        return self.data_type.to_str()

    def to_id(self, value) -> str:
        return self.data_type.to_id(value)

    def from_str(self, s: str) -> Nucleus:
        return self.data_type.from_str(s)

    def from_any_xstr(self, value) -> Nucleus:
        return self.data_type.from_any_xstr(value)

    def is_acceptable_type(self, data_type: type) -> bool:
        return issubclass(data_type, self.data_type)

    def same_values(self, value1, value2) -> bool:
        return self.data_type.same_values(value1, value2)

    def serialize(self, value: Nucleus):
        return value.serialize(self.flags_on(T.EMBEDDED))

    def deserialize(self, serialized_value) -> Nucleus:
        return self.data_type.deserialize(serialized_value)

    def choices(self):
        return self.data_type.choose_from()

class named_constant_trait(nucleus_trait, data_type = NamedConstant, base_class = True):
    s_ui_hint = Ui.choice(flags = Ui.SELECT_ONLY)

    def is_acceptable_type(self, data_type: type) -> bool:
        return data_type is self.data_type

class flags_trait(nucleus_trait, data_type = EnumBits, base_class = True):
    s_ui_hint = Ui.line()

    def is_acceptable_type(self, data_type: type) -> bool:
        return data_type is self.data_type


