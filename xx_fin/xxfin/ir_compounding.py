from xxfin.xxfin_env_vars import XXFinEnvVars

if XXFinEnvVars.use_cxxfin:
    from xxfin.cxx_ir_compounding import COMPOUND_TRANSFORM, COMPOUNDING, compounding_apply
else:
    from xxfin.py_ir_compounding import COMPOUND_TRANSFORM, COMPOUNDING, compounding_apply
