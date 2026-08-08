from core_10x.py_class import PyClass
from core_10x.traitable import NamedTsStore, TsClassAssociation

from xxfin.dev_data_helpers.data_creator import DataCreator
from xxfin.mkt_quotable import SingleMktQuote

named_stores = (
    dict(
        logical_name    = 'mkt_data',
        uri             = 'mongodb://localhost:27017/mkt_data'
    ),
)

class_associations = (
    dict(
        py_canonical_name   = PyClass.name(SingleMktQuote),     #-- all subclasses of SingleMktQuote
        ts_logical_name     = 'mkt_data',
    ),
)

def run():
    DataCreator.create(NamedTsStore, named_stores)
    DataCreator.create(TsClassAssociation, class_associations)

if __name__ == '__main__':
    run()
