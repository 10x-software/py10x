if __name__ == '__main__':
    from core_10x.code_samples.person import Person
    from infra_10x.mongodb_store import MongoStore
    from core_10x import BCache

    to_save = True


    db = MongoStore.instance(hostname='localhost', dbname='test')
    with db:
        #print(db.collection_names())

        #Person.collection().delete('Sasha|Davidovich')
        if to_save:
            p = Person(first_name = 'Sasha', last_name = 'Davidovich')
            rev = p.save()

        else:
            p = Person(first_name = 'Sasha', last_name = 'Davidovich')
            print(p.age)

            p.age = 61
            rev = p.save()
            print(p.age)

            p.age = -10
            print(p.age)

            p.reload()
            print(p.age)






