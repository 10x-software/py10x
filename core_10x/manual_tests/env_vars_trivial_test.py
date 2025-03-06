from datetime import date

from core_10x.env_vars import EnvVars, XDateTime, M

class CompanyEnvVars(EnvVars, env_name = 'YYY_LLC'):
    date_format     = M(XDateTime.FORMAT_US)

if __name__ == '__main__':
    d = date.today()
    print(XDateTime.date_to_str(d))

    #ev = EnvVars()

    df_10x = EnvVars.X.date_format
    print(XDateTime.date_to_str(d))

    df_yyy = EnvVars.YYY_LLC.date_format
    print(XDateTime.date_to_str(d))



