if __name__ == '__main__':
    from core_10x.code_samples.person import Person

    ppl_stored = [
        Person(last_name='Davidovich', first_name='Sasha', weight_lbs=170, _replace=True),
        Person(last_name='Pevzner', first_name='Ilya', weight_lbs=200, _replace=True),
        Person(last_name='Lesin', first_name='Alex', weight_lbs=190, _replace=True),
        Person(last_name='Smith', first_name='John', weight_lbs=180, _replace=True),
    ]

    id_traits = ('last_name', 'first_name')
    existing_id_traits = [{name: p.get_value(name) for name in id_traits} for p in ppl_stored]

    ppl_found = [Person.existing_instance(**id_values) for id_values in existing_id_traits]

    assert ppl_found == ppl_stored

    p1 = Person.existing_instance(last_name='Smith', first_name='John')
    assert p1

    p2 = Person.existing_instance(last_name='Smith', first_name='Josh', _throw=False)
    assert not p2

    id1 = ppl_found[0].id()
    p3 = Person.existing_instance_by_id(_id=id1)

    id1_val = id1.value
    p4 = Person.existing_instance_by_id(_id_value=id1_val)
    assert p3 == p4

    id2_val = 'Smith|Josh'
    p5 = Person.existing_instance_by_id(_id_value=id2_val, _throw=False)
    assert not p5
