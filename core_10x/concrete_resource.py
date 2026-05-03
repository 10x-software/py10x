from core_10x.named_constant import NamedConstant

from core_10x.rel_db import RelDb
from core_10x.ts_store import TsStore
#-- ... more concrete Resource subclasses

class CONCRETE_RESOURCE(NamedConstant):
    TS_STORE    = TsStore
    REL_DB      = RelDb

