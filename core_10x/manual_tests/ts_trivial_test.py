if __name__ == '__main__':
    from core_10x.code_samples.person import Person
    from infra_10x.mongodb_store import MongoStore


    db = MongoStore.instance(hostname='localhost', dbname='test')
    with db:
        #print(db.collection_names())
        p = Person(first_name='Sasha', last_name='Davidovich')
        p.save()




