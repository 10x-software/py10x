if __name__ == '__main__':
    from core_10x.environment_variables import EnvVars
    from core_10x.ts_store import TsStore
    from core_10x.code_samples.person import Person

    vault_uri = 'mongodb://localhost:27018/vault'
    main_uri  = 'mongodb://localhost:27019/main'

    EnvVars.main_ts_store_uri = main_uri
    EnvVars.main_vault_uri = vault_uri

    with TsStore.instance_from_uri('mongodb://localhost/test'):
        people = Person.load_many()

        for p in people:
            print(f'{p.full_name}: {p.age}, {p.weight}')


    p = people[0]
    p.save()