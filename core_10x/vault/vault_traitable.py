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
            raise OSError(f'XX MasterPassword for {username} is not found')

        return pwd

    @classmethod
    def keep_master_password(cls, password: str):
        username = OsUser.me.name()
        keyring.set_password(EnvVars.master_password_key, username, password)

    @classmethod
    @cache
    def retrieve_vault_password(cls, vault_uri: str) -> str:
        username = OsUser.me.name()
        pwd = keyring.get_password(vault_uri, username)
        if pwd is None:
            raise OSError(f'Password for {username} @ {vault_uri} is not found')

        return pwd

    @classmethod
    def keep_vault_password(cls, vault_uri: str, password: str):
        username = OsUser.me.name()
        keyring.set_password(vault_uri, username, password)

    @classmethod
    @cache
    def store_per_class(cls) -> TsStore:
        uri = EnvVars.var.vault_ts_store_uri.check()
        spec = TsStore.spec_from_uri(uri)
        kwargs = spec.kwargs
        ts_class = spec.resource_class
        hostname = kwargs[ts_class.HOSTNAME_TAG]
        is_running, with_auth = ts_class.is_running_with_auth(hostname)
        if not is_running or not with_auth:
            raise OSError(f'Vault host {hostname} must be run with auth')

        username = OsUser.me.name()
        kwargs[ts_class.USERNAME_TAG] = username
        kwargs[ts_class.PASSWORD_TAG] = cls.retrieve_master_password()

        return ts_class.instance(**kwargs)
