import ast
import os

from core_10x_i import OsUser

from core_10x.global_cache import cache
from core_10x.rc import RC
from core_10x.xdate_time import XDateTime, date, datetime

# ===================================================================================================================================
#   date_format: str    = default_value
#
#   def date_format_apply(cls, fmt: str):
#     XDateTime.set_default_format(fmt)
#
#   datetime_format: str
#
#   def datetime_format_get(cls):
#       return f'{cls.date_format} %H:%M%S'
#
#   def datetime_format_apply(cls, value):
#       ...
# ===================================================================================================================================


class classproperty(property):
    def __get__(self, obj, objtype: type = None):
        return self.fget(objtype)


class _EnvVars:
    # fmt: off
    s_converters = {
        bool:       lambda s: ast.literal_eval(s.lower().capitalize()),
        int:        lambda s: ast.literal_eval(s),
        float:      lambda s: ast.literal_eval(s),
        str:        lambda s: s,
        date:       lambda s: XDateTime.str_to_date(s),
        datetime:   lambda s: XDateTime.str_to_datetime(s),
    }
    # fmt: on

    @classmethod
    def _getter(cls, data_type, var_name: str, f_get, f_apply):
        # print(var_name)
        str_value = os.getenv(var_name)
        if str_value is not None:
            f_convert = cls.s_converters.get(data_type)
            assert f_convert, f'Unknown data type {data_type}'
            try:
                value = f_convert(str_value)
            except Exception as e:
                raise TypeError(f'Variable {var_name} - could not convert {str_value} to {data_type}') from e
        else:
            try:
                value = f_get(cls)
            except Exception as e:
                rc = RC(False)  # -- capture the exc
                raise RuntimeError(f'{cls}.{var_name} - failed while getting a value\n{rc.error()}') from e

        if f_apply:
            try:
                f_apply.__get__(cls)(value)
            except Exception as e:
                rc = RC(False)  # -- capture the exc
                raise ValueError(f'{cls}.{var_name} - failed while applying value: {value}\n{rc.error()}') from e

        return value

    @classmethod
    def full_getter(cls, data_type, var_name: str, f_get, f_apply):
        f = lambda cls: cls._getter(data_type, var_name, f_get, f_apply)
        # return classmethod(cache(f))
        return cache(f)

    s_env_name: str = None

    def __init_subclass__(cls, env_name: str = None, **kwargs):
        assert env_name, 'env_name is required'

        cls.s_env_name = env_name
        annotations = cls.__annotations__
        assert annotations, 'No variables are defined'

        cls_dict = cls.__dict__
        for name, data_type in annotations.items():
            def_value = cls_dict.get(name)
            if def_value is None:  # -- no default value, let's locate the getter
                f_get_name = f'{name}_get'
                f_get = cls_dict.get(f_get_name)
                assert f_get, f'Variable {name} must define either a default value or a getter {f_get_name}(cls)'
                # -- TODO: check signature: f_get(cls)
            else:
                f_get = lambda cls, def_value=def_value: def_value

            f_apply_name = f'{name}_apply'
            f_apply = cls_dict.get(f_apply_name)  # -- f(cls, value)

            var_name = f'{env_name}_{name.upper()}'
            full_getter = cls.full_getter(data_type, var_name, f_get, f_apply)
            setattr(cls, name, classproperty(full_getter))


class EnvVars(_EnvVars, env_name='XX'):
    build_area: str
    parent_build_area: str = 'dev'
    traitable_store_uri: str = 'mongodb://localhost:27017/main'
    backbone_store_class_name: str = ''  # = 'infra_10x.mongodb_store.MongoStore'
    backbone_store_host_name: str = ''  # = 'localhost'
    date_format: str = XDateTime.FORMAT_ISO

    sdlc_area: str

    def build_area_get(self) -> str:
        return OsUser.me.name()

    @classmethod
    def date_format_apply(cls, value):
        XDateTime.set_default_format(value)

    def sdlc_area_get(self) -> str:
        ba = self.build_area
        pba = self.parent_build_area
        return f'{ba}/{pba}' if pba else ba
