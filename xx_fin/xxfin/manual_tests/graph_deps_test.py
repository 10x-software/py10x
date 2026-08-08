if __name__ == '__main__':
    from datetime import date

    from xxfin.ccy import Ccy
    from xxfin.ccy_forward import CcyForward
    from xxfin.mkt_quotable import GRAPH_ON, MktDeps

    end_date = date(2035, 12, 12)
    ccy      = Ccy.existing_instance(name = 'GBP')
    cf       = CcyForward(denominated = ccy, end_date = end_date)

    with GRAPH_ON() as graph:
        py_price = cf.price

        mkt_deps = MktDeps(graph, cf.T.price)    #-- i.e., target_class = SingleMktQuote, leaf_traits = ('quote', )

        bump = 0.99
        for cls, obj_id, trait, val in mkt_deps.deps(objects = False):   #-- object IDs instead of objects
            print(f'{cls.__name__:<25}, {obj_id.value:<35}, {trait.name}: {val}')

            mkt_deps.perturb(cls, obj_id, trait, val * bump)    #-- bump the quote

        bumped_price = cf.price

    print(f'\nOriginal price: {py_price:.4f}; Bumped price: {bumped_price:.4f}')
