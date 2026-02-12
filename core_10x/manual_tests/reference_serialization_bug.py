from py10x_kernel import BTraitableProcessor

from core_10x.code_samples.person import Person
from core_10x.trait_definition import T


class MarriedPerson(Person):
    spouse: Person = T()


if __name__ == '__main__':
    from core_10x.manual_tests.reference_serialization_bug import MarriedPerson

    with BTraitableProcessor.create_root():
        MarriedPerson(first_name='Ilya', last_name='Pevzner', spouse=MarriedPerson(first_name='Tatiana', last_name='Pevzner'), _replace=True).save(
            save_references=True
        )

    assert type(MarriedPerson(first_name='Ilya', last_name='Pevzner').spouse) is MarriedPerson
