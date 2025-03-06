import os

from core_10x.traitable import Traitable, Trait, T, RC, M
from core_10x.xdate_time import XDateTime

class _EvalOnce(Traitable):
    def __init_subclass__(cls, run_time = False, **kwargs):
        super().__init_subclass__(**kwargs)
        to_set = T.EVAL_ONCE if not run_time else T.EVAL_ONCE | T.RUNTIME
        for trait in cls.s_dir.values():
            if not trait.flags_on(T.RESERVED):
                trait.set_flags(to_set.value())

class _EnvVars(_EvalOnce, run_time = True):
    s_env_name: str = None
    def __init_subclass__(cls, env_name: str = None, **kwargs):
        assert env_name, 'env_name is required'
        cls.s_env_name = env_name
        super().__init_subclass__(**kwargs)

        env_name = cls.s_env_name
        for trait_name, trait in cls.s_dir.items():
            if trait.flags_on(T.RESERVED):
                continue

            var_name = f'{env_name}_{trait_name.upper()}'
            f_apply_name = f'{trait_name}_apply'
            f_apply = getattr(cls, f_apply_name, None)
            trait.set_f_get(lambda obj, t = trait, name = var_name, f = f_apply: _getenv(obj, t, name, f), True)

        setattr(_EnvVars, env_name, cls())

        def _getenv(self, trait: Trait, var_name: str, f_apply):
            str_value = os.getenv(var_name, trait.default_value())
            try:
                value = trait.from_str(str_value)
            except Exception as e:
                raise ValueError(f"{self.__class__}.{var_name} - invalid value: '{str_value}'")

            if f_apply:
                try:
                    f_apply(self, value)
                except Exception:
                    rc = RC(False)  #-- capture the exc
                    raise ValueError(f"{self.__class__}.{var_name} - failed while applying value: {value}\n{rc.error()}")

            return value

class EnvVars(_EnvVars, env_name = 'X', run_time = True):
    date_format: str    = T(XDateTime.FORMAT_ISO)

    def date_format_apply(self, fmt: str):
        XDateTime.set_default_format(fmt)


