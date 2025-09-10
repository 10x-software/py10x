if __name__ == '__main__':
    from infra_10x.mongodb_store import MongoStore

    from core_10x.code_samples.person import Person

    to_save = True


    db = MongoStore.instance(hostname='localhost', dbname='test')
    #db.begin_using()

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






