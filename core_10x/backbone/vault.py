from datetime import datetime

from core_10x.backbone.backbone_traitable import VaultTraitable, T, RC
from core_10x.backbone.security_keys import SecKeys

class ResourceAccessor(VaultTraitable):
    resource_name: str      = T(T.ID)
    #username: str           = T(T.ID)

    login: str              = T()
    password: bytes         = T()
    last_updated: datetime  = T()

    def last_updated_get(self) -> datetime:
        return datetime.utcnow()

class Vault:
    ANY_HOST = '.'

    @staticmethod
    def save_resource_accessor(username: str, hostname: str, login: str, password: str, public_key = None) -> RC:
        assert login and password, 'login and password must not be empty'

        pwd = SecKeys.encrypt(password, public_key = public_key)
        if pwd is None:
            return RC(False, 'Security Keys are missing. If you are using a new computer, please run "xx user new machine" from your shell')

        ra = ResourceAccessor(hostname = hostname)
        ra.reload()
        rc = ra.set_values(login = login, password = pwd)
        if not rc:
            return rc

        ra.save()
