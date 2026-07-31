from core_10x.environment_variables import _EnvVars

class XXCommonEnvVars(_EnvVars, env_name = 'XXCOMMON'):
    use_cxx_curve: bool = False
