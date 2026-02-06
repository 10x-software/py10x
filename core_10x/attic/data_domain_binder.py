from core_10x.environment_variables import EnvVars
from core_10x.global_cache import cache
from core_10x.py_class import PyClass


# ===================================================================================================================================
#   Data Domain Bindings
#
#   from core_10x.data_domain import GeneralDomain
#   from xxx.yyy.mdu_domain import MDU
#   ...
#   DATA_DOMAIN_BINDINGS = dict(
#       dev = {
#           GeneralDomain: dict(
#               GENERAL             = R(TS_STORE.MONGO_DB,          hostname = 'dev.mongo.general.io', tsl = True, ...),
#           ),
#
#           MDU:    dict(
#               SYMBOLOGY           = R(REL_DB.ORACLE_DB,           hostname = 'dev.oracle.io', a = '...', b = '...'),
#               MKT_CLOSE_CLUSTER   = R(CLOUD_CLUSTER.RAY_CLUSTER,  hostname = 'dev.ray1.io', ...),
#           ),
#       },
#
#       prod = {
#           GeneralDomain: dict(
#               GENERAL             = R(TS_STORE.MONGO_DB,          hostname = 'prod.mongo.general.io', tsl = True, ...),
#           ),
#
#           MDU:    dict(
#               SYMBOLOGY           = R(REL_DB.ORACLE_DB,           hostname = 'prod.oracle.io', a = '...', b = '...'),
#               MKT_CLOSE_CLUSTER   = R(CLOUD_CLUSTER.RAY_CLUSTER,  hostname = 'prod.ray2.io', ...),
#           ),
#       },
#
#   )
# ===================================================================================================================================
class DataDomainBinder:
    @staticmethod
    @cache
    def all_bindings() -> dict:
        dd_bindings_symbol = EnvVars.data_domain_bindings
        if not dd_bindings_symbol:
            return None

        return PyClass.find_symbol(dd_bindings_symbol)
