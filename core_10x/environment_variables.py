import ast
import os

from py10x_kernel import OsUser

from core_10x.global_cache import cache
from core_10x.rc import RC
from core_10x.xdate_time import XDateTime, date, datetime
from core_10x.exec_control import GRAPH_ON, GRAPH_OFF
#from core_10x.resource import Resource

#===================================================================================================================================
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
#===================================================================================================================================


class classproperty(property):
    def __get__(self, obj, objtype: type = None):
        return self.fget(objtype)


class _EnvVars:
    class Var:
        def __init__(self, env_var_class, attr_name: str, value = None):
            self.env_var_class = env_var_class
            self.attr_name = attr_name
            if value is None:
                value = getattr(env_var_class, attr_name)
            self.value = value

        def __bool__(self):
            return bool(self.value)

        def check(self, f = None, err = 'is not defined'):
            value = self.value
            rc = bool(value) if not f else f(value)
            if not rc:
                raise ValueError(f'{self.env_var_class.var_name(self.attr_name)} {err}')

            return value

    s_converters = {
        bool:       lambda s: ast.literal_eval(s.lower().capitalize()),
        int:        lambda s: ast.literal_eval(s),
        float:      lambda s: ast.literal_eval(s),
        str:        lambda s: s,
        date:       lambda s: XDateTime.str_to_date(s),
        datetime:   lambda s: XDateTime.str_to_datetime(s),
        #Resource:   lambda s: Resource
    }

    @classmethod
    def _getter(cls, data_type, var_name: str, f_get, f_apply):
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
                rc = RC(False)  #-- capture the exc
                raise ValueError(f'{cls}.{var_name} - failed while applying value: {value}\n{rc.error()}') from e

        return value

    @classmethod
    def full_getter(cls, data_type, var_name: str, f_get, f_apply):
        f = lambda cls: cls._getter(data_type, var_name, f_get, f_apply)
        # return classmethod(cache(f))
        return cache(f)

    @classmethod
    def create_var_name(cls, env_name: str, attr_name: str) -> str:
        return f'{env_name}_{attr_name.upper()}'

    @classmethod
    def var_name(cls, var_or_name) -> str:
        if isinstance(var_or_name, cls.Var):
            var_or_name = var_or_name.attr_name
        return cls.create_var_name(cls.s_env_name, var_or_name)

    s_env_name: str = None
    var = None
    def __init_subclass__(cls, env_name: str = None, **kwargs):
        assert env_name, 'env_name is required'

        cls.s_env_name = env_name
        annotations = cls.__annotations__
        assert annotations, 'No variables are defined'

        cls_dict = cls.__dict__
        for name, data_type in annotations.items():
            default_value = cls_dict.get(name)
            if default_value is None:  # -- no default value, let's locate the getter
                f_get_name = f'{name}_get'
                f_get = cls_dict.get(f_get_name)
                assert f_get, f'Variable {name} must define either a default value or a getter {f_get_name}(cls)'
                # -- TODO: check signature: f_get(cls)
            else:
                f_get = lambda cls, def_value = default_value: def_value

            f_apply_name = f'{name}_apply'
            f_apply = cls_dict.get(f_apply_name)  # -- f(cls, value)

            var_name = cls.create_var_name(env_name, name)
            full_getter = cls.full_getter(data_type, var_name, f_get, f_apply)
            setattr(cls, name, classproperty(full_getter))

            cls.var = cls.AccessVar(cls)

    class AccessVar:
        def __init__(self, env_vars_class):
            self.env_vars_class = env_vars_class

        def __getattr__(self, item):
            cls = self.env_vars_class
            value = getattr(cls, item)
            if value is None:
                raise AssertionError(f'Unknown var name {item}')

            return _EnvVars.Var(cls, item, value)

class EnvVars(_EnvVars, env_name='XX'):
    build_area: str
    parent_build_area: str          = 'dev'

    master_password_key: str        = 'XX_MASTER_PASSWORD'

    #examples_ts_store_uri: str      = ''            #-- e.g., mongodb://localhost/examples
    vault_ts_store_uri: str         = ''            #-- to store/auto retrieve security credentials for each user/resource; default is main_ts_store_uri
    main_ts_store_uri: str          = ''            #-- e.g., 'mongodb://localhost:27018/main'
    use_ts_store_per_class: bool    = True          #-- use TsStore per Traitable class associations
    functional_account_prefix: str  = 'xx'          #-- used in user names to distinguish a regular user name from a functional account

    graph_on: bool                  = False         #-- whether GRAPH is ON by default

    date_format: str = XDateTime.FORMAT_ISO

    sdlc_area: str

    def vault_ts_store_uri_get(self) -> str:
        return self.main_ts_store_uri

    def build_area_get(self) -> str:
        return OsUser.me.name()

    @classmethod
    def date_format_apply(cls, value):
        XDateTime.set_default_format(value)

    def sdlc_area_get(self) -> str:
        ba = self.build_area
        pba = self.parent_build_area
        return f'{ba}/{pba}' if pba else ba
