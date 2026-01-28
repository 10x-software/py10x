from core_10x.traitable import Traitable, T, TsClassAssociation, NamedTsStore, TsStore
from core_10x.code_samples.person import Person

class Dummy(Traitable):
    text: str = T()

class Dummy1(Traitable):
    text: str   = T()

class Dummy2(Dummy):
    ...

if __name__ == '__main__':
    from core_10x.manual_tests.ts_class_association_test import Dummy, Dummy1, Dummy2
    from core_10x.py_class import PyClass

    extra_uris = dict(
        dummy = 'mongodb://localhost/dummy',
        dummy2 = 'mongodb://localhost/dummy2',
    )
    for name, uri in extra_uris.items():
        #store = TsStore.instance_from_uri(uri)
        ns = NamedTsStore(_force = True,
            logical_name    = name,
            uri             = uri,
        )
        ns.save().throw()

    TsClassAssociation(_force = True,
        py_canonical_name   = PyClass.name(Dummy),
        ts_logical_name     = 'dummy',
    ).save().throw()
    TsClassAssociation(_force = True,
        py_canonical_name   = PyClass.name(Dummy1),
        ts_logical_name     = 'dummy1',
    ).save().throw()

    d1 = Dummy1(text = 'hello dummy1')
    d1.save().throw()

    d2 = Dummy2(text = 'hello dummy2')
    d2.save().throw()

    p = Person(first_name = 'A', last_name = 'B')
    p.save().throw()
