from core_10x_i import BTraitableProcessor
from infra_10x.mongodb_store import MongoStore

from core_10x.code_samples.person import Person
from core_10x.trait_definition import T


class MarriedPerson(Person):
    spouse: Person = T()


if __name__ == '__main__':
    db = MongoStore.instance(hostname='localhost', dbname='test')
    db.begin_using()

    with BTraitableProcessor.create_root():
        MarriedPerson(first_name='Ilya', last_name='Pevzner', spouse=MarriedPerson(first_name='Tatiana', last_name='Pevzner'), _replace=True).save(
            save_references=True
        )

    assert type(MarriedPerson(first_name='Ilya', last_name='Pevzner').spouse) is MarriedPerson
