from core_10x.environment_variables import _EnvVars


class XXFinEnvVars(_EnvVars, env_name = 'XXFIN'):
    default_pricing_context_name: str   = ''

    #cxx_day_count_convention: bool = False
    use_cxxfin: bool = False
    aadc_license: str = ''  # unused for now -- reserved to help locate the AADC_NG_LICENSE file
