if __name__ == '__main__':
    from core_10x.code_samples.person import Person
    from infra_10x.mongodb_store import MongoStore

    to_save = True


    db = MongoStore.instance(hostname='localhost', dbname='test')
    #db.s_resource_type.begin_using(db)

    with db:
        #print(db.collection_names())

        #Person.collection().delete('Sasha|Davidovich')
        if to_save:
            p = Person(first_name = 'Sasha', last_name = 'Davidovich')
            p.weight_lbs=200
            rev = p.save()

        else:
            p = Person(first_name = 'Sasha', last_name = 'Davidovich')
            p.weight_lbs=200

            print(p.age)

            p.age = 61
            rev = p.save()
            print(p.age)

            p.age = -10
            print(p.age)

            p.reload()
            print(p.age)






