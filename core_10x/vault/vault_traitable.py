import keyring

from core_10x_i import OsUser

from core_10x.traitable import Traitable, T, RT, RC, RC_TRUE, TsStore, cache
from core_10x.environment_variables import EnvVars

class VaultTraitable(Traitable):
    @classmethod
    @cache
    def retrieve_master_password(cls) -> str:
        username = OsUser.me.name()
        pwd = keyring.get_password(EnvVars.master_password_key, username)
        if pwd is None:
            raise EnvironmentError(f'XX MasterPassword for {username} is not in the Vault')

        return pwd

    @classmethod
    def keep_master_password(cls, password: str):
        username = OsUser.me.name()
        keyring.set_password(EnvVars.master_password_key, username, password)

    @classmethod
    @cache
    def store(cls) -> TsStore:
        uri = EnvVars.assert_var.vault_ts_store_uri
        spec = TsStore.spec_from_uri(uri)
        kwargs = spec.kwargs
        ts_class = spec.resource_class
        hostname = kwargs[ts_class.HOSTNAME_TAG]
        is_running, with_auth = ts_class.is_running_with_auth(hostname)
        if not is_running or not with_auth:
            raise EnvironmentError(f'Vault host {hostname} must be run with auth')

        username = OsUser.me.name()
        kwargs[ts_class.USERNAME_TAG] = username
        kwargs[ts_class.PASSWORD_TAG] = cls.retrieve_master_password()

        return ts_class.instance(**kwargs)
