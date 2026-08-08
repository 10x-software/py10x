from xxfin.xxfin_env_vars import XXFinEnvVars

if XXFinEnvVars.use_cxxfin:
    from xxfin.cxx_day_count_convention import DAY_COUNT_CONVENTION, dc_fractions_for_dates
else:
    from xxfin.py_day_count_convention import DAY_COUNT_CONVENTION, dc_fractions_for_dates

