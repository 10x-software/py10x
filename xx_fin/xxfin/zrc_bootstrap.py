from xxfin.xxfin_env_vars import XXFinEnvVars

if XXFinEnvVars.use_cxxfin:
    from xxfin.cxx_zrc_bootstrap import solve_cash_deposit, solve_swap
else:
    from xxfin.py_zrc_bootstrap import solve_cash_deposit, solve_swap
