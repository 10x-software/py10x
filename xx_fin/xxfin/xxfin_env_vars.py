from core_10x.environment_variables import _EnvVars


class XXFinEnvVars(_EnvVars, env_name = 'XXFIN'):
    default_pricing_context_name: str   = ''

    verify_ccy: bool = True

    #cxx_day_count_convention: bool = False
    use_cxxfin: bool = False
    aadc_license: str = ''

    @classmethod
    def verify_ccy_apply(cls, value):
        from xxfin.ccy import Ccy

        Ccy.verified.clear()