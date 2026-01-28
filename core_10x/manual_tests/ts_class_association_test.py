from core_10x.code_samples.person import Person
from core_10x.traitable import NamedTsStore, T, Traitable, TsClassAssociation, TsStore


class Dummy1(Traitable):
    text: str   = T(T.ID)

class Dummy2(Traitable):
    text: str   = T(T.ID)

class Dummy3(Dummy2):
    ...

if __name__ == '__main__':
    from core_10x.manual_tests.ts_class_association_test import Dummy1, Dummy2, Dummy3
    from core_10x.py_class import PyClass
    from core_10x.environment_variables import EnvVars

    #-- 0) Create a Person instance and save - must go to the main TsStore - no association
    p = Person(first_name = 'A', last_name = 'B')
    p.save().throw()
    db = TsStore.instance_from_uri(EnvVars.main_ts_store_uri)
    with db:
        assert Person.exists_in_store(p.id()), f'Person must have been stored to {EnvVars.main_ts_store_uri}'

    #-- 1) Create NamedTsStore objects referring to all available extra TsStores for Class Associations
    extra_uris = dict(
        dummy1 = 'mongodb://localhost/dummy1',
        dummy2 = 'mongodb://localhost/dummy2',
    )
    for name, uri in extra_uris.items():
        #store = TsStore.instance_from_uri(uri)
        ns = NamedTsStore(_replace = True,
            logical_name    = name,
            uri             = uri,
        )
        ns.save().throw()

    #-- 2) Create Class Association for Dummy1 - explicit association for the class
    TsClassAssociation(_replace = True,
        py_canonical_name   = PyClass.name(Dummy1),
        ts_logical_name     = 'dummy1',
    ).save().throw()

    #-- 3) Create Class Association for Dummy2 - explicit association for the class
    TsClassAssociation(_replace = True,
        py_canonical_name   = PyClass.name(Dummy2),
        ts_logical_name     = 'dummy2',
    ).save().throw()

    #-- 4) Create an instance of Dummy1 and save it - must go to dummy1 TsStore
    d1 = Dummy1(text = 'hello dummy1')
    d1.save().throw()
    db1 = TsStore.instance_from_uri(extra_uris['dummy1'])
    with db1:
        assert Dummy1.exists_in_store(d1.id()), f'Dummy1 must have been associated with {extra_uris["dummy1"]}'

    #-- 5) Create an instance of Dummy3 and save it - must go to dummy2 TsStore because it deriuves from Dummy2 which is associated with dummy2 TsStore
    d3 = Dummy3(text = 'hello dummy3')
    d3.save().throw()
    db2 = TsStore.instance_from_uri(extra_uris['dummy2'])
    with db2:
        assert Dummy3.exists_in_store(d3.id()), f'Dummy3 must have been associated with {extra_uris["dummy2"]}'

