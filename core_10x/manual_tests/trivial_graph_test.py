if __name__ == '__main__':
    from core_10x.code_samples.person import Person
    from core_10x.exec_control import GRAPH_ON, GRAPH_OFF

    with GRAPH_ON(convert_values = True, debug = True) as graph:
        p = Person(first_name = 'John', last_name = 'Smith')

        print(p.full_name)
        p.dob = '19630514'
        p.weight_lbs = 170

        ser = p.serialize(True)

    print(p)
