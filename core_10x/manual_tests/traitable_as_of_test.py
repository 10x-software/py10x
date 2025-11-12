from __future__ import annotations

from datetime import date, datetime

from infra_10x.mongodb_store import MongoStore

from core_10x.code_samples.person import Person
from core_10x.exec_control import GRAPH_OFF, GRAPH_ON
from core_10x.rc import RC, RC_TRUE
from core_10x.traitable import THIS_CLASS, AsOfContext, T


class MarriedPerson(Person):
    spouse: THIS_CLASS = T()
    # @classmethod
    # def load_data(cls, id: ID) -> dict | None:
    #     serialized_traitable = super().load_data(id)
    #     print(f'loaded {id} -> {serialized_traitable}')
    #     return serialized_traitable
    #
    # @classmethod
    # def deserialize(cls, serialized_data) -> Traitable:
    #     traitable = super().deserialize(serialized_data)
    #     print(f'deserialized {serialized_data}')
    #     return traitable

    def spouse_set(self,trait,spouse) -> RC:
        self.raw_set_value(trait,spouse)
        if spouse:
            spouse.raw_set_value(trait,self)
        return RC_TRUE


if __name__=='__main__':
    with MongoStore.instance(hostname="localhost", dbname="traitable_history_test"):
        MarriedPerson.delete_collection()
        MarriedPerson.s_history_class.delete_collection()

        with GRAPH_ON():
            # Create and save a person
            person = MarriedPerson(first_name="Alyssa", last_name="Lees", dob=date(1985,7,5))
            person.spouse = MarriedPerson(first_name="James", last_name="Bond", dob=date(1985,7,5))
            person.spouse.save()
            person.save()

            ts = datetime.utcnow()

            # Update and save again
            person.dob=date(1985,7,6)
            person.spouse.dob=date(1985,7,6)
            person.save().throw()
            person.spouse.save().throw()

            person_id = person.id()
            print(person.serialize_object())
            #del person
            #gc.collect()


        #with GRAPH_ON():

        #with CACHE_ONLY():
        #    assert not MarriedPerson.existing_instance_by_id(person_id,_throw=False)

        # with INTERACTIVE():
        #     person1 = MarriedPerson(person_id)
        #     print(person1.serialize_object())
        #     assert person1.dob == date(1985, 7, 6)
        #
        #     assert person1.spouse
        #     assert person1.spouse.dob == date(1985, 7, 6)
        #
        # with INTERACTIVE():
        #     person_as_of = MarriedPerson.as_of(person_id,as_of_time=ts)
        #     assert person_as_of.dob == date(1985, 7, 5)
        #     assert person_as_of.spouse.dob == date(1985, 7, 5)


        for ctx in (
                #INTERACTIVE,
                GRAPH_ON,
                GRAPH_OFF,
        ):
            for as_of in (
                    ts,
                    None,
            ):
                for check_nested_inside in (
                    True,
                    False,
                ):
                    with ctx():
                        with AsOfContext([MarriedPerson],as_of_time=as_of):
                            person2 = MarriedPerson(person_id)
                            print(f'{as_of is None}:{check_nested_inside}:{ctx.__name__}: created person2:')
                            assert person2.dob == (date(1985, 7, 5 + (as_of is None)))
                            print(f'{as_of is None}:{check_nested_inside}:{ctx.__name__}: checked person2.dob')
                            if check_nested_inside:
                                assert person2.spouse.dob == (date(1985, 7, 5 + (as_of is None)))
                                print(f'{as_of is None}:{check_nested_inside}:{ctx.__name__}: checked person2.spouse.dob')

                        print(f'{as_of is None}:{check_nested_inside}:{ctx.__name__}: exited context')
                        assert person2.spouse.dob == date(1985, 7, 6)

        #TODO: (alternatives)
        # a) force reference load when deserializing from history
        # b) force reference load on context exit (keep weak refs to lazy refs)
        # c) assert no refs at exit
        # d) optional on-graph layer/context exit (no leakage outside context)
        # e) "break" refs on exit to make them non-loadable (with a possibility to repair)
        # f) attach context to refs and use when loading them? [[same semantics as forcing reference load]]
        # ?? what if rference created outside context (but not loaded); then created again within context

        # CLEAN - new BTP.create(-1,-1,-1,use_parent_cache=False,use_default_cache=False) ==> create new default cache!
        # How o create parentless BTP?

        # TODO FUTURE - current state as history query

        # DEFAULT_CACHE - add




        ## interface - AsOfContext
        ## semantics..

