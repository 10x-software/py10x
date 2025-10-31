from datetime import date, datetime

from infra_10x.mongodb_store import MongoStore

from core_10x.code_samples.person import Person
from core_10x.rc import RC, RC_TRUE
from core_10x.traitable import THIS_CLASS, AsOfContext, T


class MarriedPerson(Person):
    spouse: THIS_CLASS = T()
    def spouse_set(self,trait,spouse) -> RC:
        self.raw_set_value(trait,spouse)
        spouse.raw_set_value(trait,self)
        return RC_TRUE


if __name__=='__main__':
    with MongoStore.instance(hostname="localhost", dbname="traitable_history_test"):
        MarriedPerson.delete_collection()
        MarriedPerson.s_history_class.delete_collection()

        # Create and save a person
        person = MarriedPerson(first_name="Alyssa", last_name="Lees", dob=date(1985,7,5))
        person.spouse = MarriedPerson(first_name="James", last_name="Bond", dob=date(1985,7,5))
        person.spouse.save()
        person.save()

        ts = datetime.utcnow()

        # Update and save again
        person.dob=date(1985,7,6)
        person.spouse.dob=date(1985,7,6)
        person.save()
        person.spouse.save()

        person_as_of = MarriedPerson.as_of(person.id(),as_of_time=ts)
        assert person.dob == date(1985, 7, 5)
        assert person.spouse.dob == date(1985, 7, 6)

        with AsOfContext([MarriedPerson],as_of_time=ts):
            person.reload()
            person.spouse.reload()
            assert person.dob == date(1985, 7, 5)
            assert person.spouse.dob == date(1985, 7, 6)
