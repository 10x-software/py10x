import inspect

from core_10x.trait_definition import T


class X:
    user_id: str    = T(T.ID | T.RUNTIME)   #, Ui('User ID', tip = 'OS login', min_width = 50))
    age: int        = T()
    #model: any      = RT()


annotations = inspect.get_annotations(X)

#dir = TraitDefinition.dir( X.__dict__, annotations, {} )

#tdef: TraitDefinition = dir['user_id']

# t = Trait(tdef)
# t2 = copy.deepcopy(t)