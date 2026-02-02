import ast
import os

from core_10x_i import OsUser

from core_10x.global_cache import cache
from core_10x.rc import RC
from core_10x.xdate_time import XDateTime, date, datetime
from core_10x.resource import Resource

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
        #Resource:   lambda s: Resource
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
    assert_var = None

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

            cls.assert_var = cls.AssertVar(cls)

    class AssertVar:
        def __init__(self, env_vars_class):
            self.env_vars_class = env_vars_class

        def __getattr__(self, item):
            value = getattr(self.env_vars_class, item)
            if not value:
                raise AssertionError(f'{self.env_vars_class.s_env_name}_{item.upper()} is not defined')
            return value


class EnvVars(_EnvVars, env_name='XX'):
    # fmt: off
    build_area: str
    parent_build_area: str          = 'dev'

    master_password_key: str        = 'XX_MASTER_PASSWORD'

    examples_ts_store_uri: str      = ''            #-- e.g., mongodb://localhost/examples
    vault_ts_store_uri: str         = ''            #-- if defined, used to store/auto retrieve security credentials for each user/resource
    main_ts_store_uri: str          = ''            #-- e.g., 'mongodb://localhost:27018/main'
    use_ts_store_per_class: bool    = True          #-- use TsStore per Traitable class associations
    functional_account_prefix: str  = 'xx'          #-- used in user names to distinguish a regular user name from a functional account

    date_format: str = XDateTime.FORMAT_ISO

    sdlc_area: str
    # fmt: on

    def build_area_get(self) -> str:
        return OsUser.me.name()

    @classmethod
    def date_format_apply(cls, value):
        XDateTime.set_default_format(value)

    def sdlc_area_get(self) -> str:
        ba = self.build_area
        pba = self.parent_build_area
        return f'{ba}/{pba}' if pba else ba
