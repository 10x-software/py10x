from core_10x.traitable import VaultUser, VaultResourceAccessor, TsStore
from core_10x.vault_utils import VaultUtils
from core_10x.environment_variables import EnvVars

from infra_10x.mongodb_store import MongoStore

if __name__ == '__main__':
    #EnvVars.vault_ts_store_uri

    #vault = MongoStore.instance(hostname = 'localhost', dbname = 'vault', port = 27018, username = 'AMD', password = '')
    VaultUtils.new_vault()
