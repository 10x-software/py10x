from datetime import date, datetime

from infra_10x.mongodb_store import MongoStore

from core_10x.code_samples.person import Person

if __name__ == '__main__':
    with MongoStore.instance(hostname='localhost', dbname='traitable_history_test'):
        Person.delete_collection()
        Person.s_history_class.delete_collection()

        # Create and save a person
        person = Person(first_name='Alyssa', last_name='Lees', dob=date(1985, 7, 5), _force=True)
        person.save()

        ts = datetime.utcnow()

        # Update and save again
        person.dob = date(1985, 7, 6)
        person.save()

        # Check history
        history = Person.history()

        # Verify server-side fields
        for entry in history:
            print(f'  - Revision {entry["_traitable_rev"]}: {entry["first_name"]} (dob: {entry["dob"]})')
            print(f'    _who: {entry["_who"]}, _at: {entry["_at"]}')

        assert person.dob == date(1985, 7, 6)

        print(Person.restore(person.id(), timestamp=ts))
        assert person.dob == date(1985, 7, 5)

        person.reload()
        assert person.dob == date(1985, 7, 6)

        print(Person.restore(person.id(), timestamp=ts, save=True))
        assert person.dob == date(1985, 7, 5)
        person.reload()
        assert person.dob == date(1985, 7, 5)
