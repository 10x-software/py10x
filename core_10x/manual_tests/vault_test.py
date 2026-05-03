if __name__ == '__main__':
    from core_10x.environment_variables import EnvVars
    from core_10x.ts_store import TsStore
    from core_10x.code_samples.person import Person

    vault_uri = 'mongodb://localhost:27018/vault'
    main_uri  = 'mongodb://localhost:27019/main'

    EnvVars.main_ts_store_uri = main_uri
    EnvVars.main_vault_uri = vault_uri

    p = Person(
        _replace = True,
        first_name = 'John',
        last_name = 'Doe',
        weight = 200.0,
    )
    p.save()