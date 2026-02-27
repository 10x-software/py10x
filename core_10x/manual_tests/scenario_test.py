if __name__ == '__main__':
    from datetime import date

    from core_10x.scenario import Scenario
    from core_10x.code_samples.person import Person

    p = Person(
        _replace = True,
        last_name   = 'Smith',
        first_name  = 'John',
        dob         = date(1970, 3, 12),
        weight      = 170.
    )
    print(f'No scenario: {p.weight}')

    fn = p.full_name
    with Scenario(fn):
        p.weight = 180.
        print(f'In Scenario({fn}): {p.weight}')

    print(f'No scenario: {p.weight}')
    with Scenario(fn):
        print(f'In Scenario({fn}): {p.weight}')

