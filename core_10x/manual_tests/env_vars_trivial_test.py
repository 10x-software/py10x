
if __name__ == '__main__':
    from datetime import date

    from core_10x.environment_variables import EnvVars, XDateTime

    d = date.today()
    print(XDateTime.date_to_str(d))

    df_10x = EnvVars.date_format
    print(XDateTime.date_to_str(d))

