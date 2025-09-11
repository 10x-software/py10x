import polars as pl
from infra_10x.mongodb_store import MongoStore

from core_10x.code_samples.person import Person

if __name__=='__main__':
    with MongoStore.instance(hostname ='localhost', dbname='test', username='', password=''):
        objs = Person.load_many()
        df = pl.DataFrame([o.serialize_object() for o in objs])
        print(df)
        df.write_database('people',connection="postgresql:///postgres?host=/tmp",engine='adbc',if_table_exists='replace')

        df2 = pl.read_database('people',connection="postgresql:///postgres?host=/tmp",engine='adbc')
        print(df2)