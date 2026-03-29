if __name__ == '__main__':
    from datetime import date

    from core_10x.code_samples.person import Person, T
    from core_10x.jit.optimization_helper import OptimizationHelper, RC

    oh = OptimizationHelper(traitable_class = Person)
    rc = RC(True)

    p = Person(_replace = True, last_name = 'Optimization', first_name  = 'Helper', weight = 250., dob = date(2000, 1, 1))
    rc <<= oh.add_object(p, _save = False)

    p_w = Person(_replace = True, last_name = 'Optimization', first_name  = 'Weight', weight = 170.)
    rc <<= oh.add_object(p_w, attr_name = 'weight', _save = False)

    p_d = Person(_replace = True, last_name = 'Optimization', first_name  = 'Dob', dob = date(1980, 7, 15))
    rc <<= oh.add_object(p_d, attr_name = 'dob', _save = False)

    if rc:
        oh.save()

    p_d_2 = oh.get_object('dob')
    assert p_d_2 == p_d

    p_2 = OptimizationHelper.get_helper(Person)
    assert p_2 == p
