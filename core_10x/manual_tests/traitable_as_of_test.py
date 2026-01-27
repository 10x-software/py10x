from __future__ import annotations

from datetime import date, datetime

import pytest
from infra_10x.mongodb_store import MongoStore
from typing_extensions import Self

from core_10x.code_samples.person import Person
from core_10x.exec_control import BTP, CACHE_ONLY, GRAPH_OFF, GRAPH_ON, INTERACTIVE
from core_10x.rc import RC, RC_TRUE
from core_10x.traitable import AsOfContext, T


class MarriedPerson(Person):
    spouse: Self = T()

    def spouse_set(self, trait, spouse) -> RC:
        self.raw_set_value(trait, spouse)
        if spouse:
            spouse.raw_set_value(trait, self)
        return RC_TRUE


if __name__ == '__main__':
    with MongoStore.instance(hostname='localhost', dbname='traitable_history_test'):
        MarriedPerson.delete_collection()
        MarriedPerson.s_history_class.delete_collection()

        with BTP.create_root():
            # Create and save a person
            person = MarriedPerson(first_name='Alyssa', last_name='Lees', dob=date(1985, 7, 5), _replace=True)
            person.spouse = MarriedPerson(first_name='James', last_name='Bond', dob=date(1985, 7, 5), _replace=True)
            person.spouse.save()
            person.save()

            ts = datetime.utcnow()

            # Update and save again
            person.dob = date(1985, 7, 6)
            person.spouse.dob = date(1985, 7, 6)
            person.save(save_references=True).throw()

            person_id = person.id()
            print(person.serialize_object())

        with CACHE_ONLY():
            assert not MarriedPerson.existing_instance_by_id(person_id, _throw=False)

        for ctx in (
            INTERACTIVE,
            GRAPH_ON,
            GRAPH_OFF,
        ):
            for as_of in (
                ts,
                None,
            ):
                with ctx():
                    person1 = MarriedPerson(person_id)
                    assert person1.dob == date(1985, 7, 6)

                    person_as_of = MarriedPerson.as_of(person_id, as_of_time=ts)

                    with AsOfContext([MarriedPerson], as_of_time=as_of):
                        with pytest.raises(RuntimeError, match=r'MarriedPerson/Alyssa|Lees: object not usable - origin cache is not reachable'):
                            _ = person1.dob

                        with pytest.raises(RuntimeError, match=r'MarriedPerson/Alyssa|Lees: object not usable - origin cache is not reachable'):
                            _ = person_as_of.dob

                        person2 = MarriedPerson(person_id)
                        assert person2.dob == (date(1985, 7, 5 + (as_of is None)))
                        assert person2.spouse.dob == (date(1985, 7, 5 + (as_of is None)))

                    assert person1.spouse.dob == date(1985, 7, 6)
                    assert person_as_of.dob == date(1985, 7, 5)

                    assert person_as_of.spouse.dob == date(1985, 7, 6)  # note - since no AsOfContext was used, nested objects are not loaded "as_of".

                    with pytest.raises(RuntimeError, match=r'MarriedPerson/Alyssa|Lees: object not usable - origin cache is not reachable'):
                        _ = person2.dob
