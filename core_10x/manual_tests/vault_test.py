from core_10x.traitable import VaultUser, VaultResourceAccessor, TsStore
from core_10x.vault_utils import VaultUtils
from core_10x.environment_variables import EnvVars

from core_10x.code_samples.person import Person

if __name__ == '__main__':

    vault_uri = 'mongodb://localhost:27018/vault'

    # EnvVars.main_vault_uri      = vault_uri
    #EnvVars.main_ts_store_uri   = 'mongodb://localhost:27019/main'
    EnvVars.main_ts_store_uri   = 'mongodb://localhost/test'


    vault = TsStore.instance_from_uri(vault_uri, username = 'amd', password = 'Onecity1love')
    with vault:
        u = VaultUser()

