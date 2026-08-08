from xxcommon.xxcommon_env_vars import XXCommonEnvVars

from xxfin.xxfin_env_vars import XXFinEnvVars

if XXFinEnvVars.use_cxxfin and XXCommonEnvVars.use_cxx_curve:
    from xxfin.cxx_rate_curve import RateCurve
else:
    from xxfin.py_rate_curve import RateCurve

from xxfin.py_rate_curve import AccrualRatioCurve
