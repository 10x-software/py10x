from core_10x_i import OsUser

from core_10x.global_cache import cache
from core_10x.environment_variables import EnvVars
from core_10x.ts_store import TsStore

class BackboneStore:
    @classmethod
    @cache
    def store(self, username: str = None, password: str = None) -> TsStore:
        if username is None:    #-- TODO: retrieve current OS user's credentials
            ##username = OsUser.me.name()
            username = ''
            password = ''

        assert username and password, 'username and password must be provided'

        cls_name = EnvVars.backbone_store_class_name
        store_cls = TsStore.store_class(cls_name)
        hostname = EnvVars.backbone_store_host_name

        return store_cls.instance(hostname = hostname, dbname = '_backbone', username = username, password = password)

