from datetime import datetime

from core_10x.xnone import XNone
from core_10x.resource import Resource
from core_10x.vault.vault_traitable import VaultTraitable, T, RT
from core_10x.vault.vault_user import VaultUser

class ResourceAccessor(VaultTraitable):
    # fmt: off
    username: str           = T(T.ID)
    resource_uri: str       = T(T.ID)

    login: str              = T()
    password: bytes         = T()

    last_updated: datetime  = T(T.EVAL_ONCE)

    user: VaultUser         = RT(T.EVAL_ONCE)
    resource: Resource      = RT(T.EVAL_ONCE)
    # fmt: on

    def username_get(self) -> str:
        return VaultUser.myname()

    def last_updated_get(self) -> datetime:
        return datetime.utcnow()

    def user_get(self) -> VaultUser:
        return VaultUser.existing_instance(user_id = self.username)

    def resource_get(self) -> Resource:
        return Resource.instance_from_uri(
            self.resource_uri,
            username = self.username,
            password = self.user.sec_keys.decrypt_text(self.password)
        )

class Vault:
    @classmethod
    def save_resource_accessor(cls, resource_uri: str, password: str, login: str = None, username: str = XNone):
        if login is None:
            login = username

        ra = ResourceAccessor(username = username, resource_uri = resource_uri)
        user = ra.user
        ra.set_values(
            login = login,
            password = user.sec_keys.encrypt_text(password)
        ).throw()

        ra.save().throw()

    #-- strictly speaking this method isn't necessary as it just returning existing_instance()
    @classmethod
    def retrieve_resource_accessor(cls, resource_uri: str, username: str = XNone) -> ResourceAccessor:
        return ResourceAccessor.existing_instance(username = username, resource_uri = resource_uri)
