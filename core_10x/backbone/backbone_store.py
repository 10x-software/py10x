from core_10x_i import OsUser

from core_10x.global_cache import cache
from core_10x.environment_variables import EnvVars
from core_10x.ts_store import TsStore

class BackboneStore:
    """
    Backbone Store instance should exist for every build area. It may be run with or without authentication required.
    If authentication is required, it must have a special-purpose user SIDEKICK with read-only permissions and must have the following databases:
    - admin
    - _backbone_    - collections:
        - bound data domains;
        - users;
        - user groups;
        - ...
    - _vault_       - collections of Resource Accessors (per username)
    - _shadow_      - collections of 'Shadow' (user-password-encrypted private key) for each user (for exporting sec keys for a new user's computer)

    """
    SIDEKICK_USER       = 'sidekick'
    BACKBONE_DB_NAME    = '_backbone_'
    VAULT_DB_NAME       = '_vault_'
    SHADOW_DB_NAME      = '_shadow_'

    @classmethod
    @cache
    def bb_store(cls) -> TsStore:   #-- BB Store
        cls_name = EnvVars.backbone_store_class_name
        cls.hostname = hostname = EnvVars.backbone_store_host_name
        if not cls_name or not hostname:
            return None

        cls.store_cls = store_cls = TsStore.store_class(cls_name)

        is_running, with_auth = store_cls.is_running_with_auth(hostname)
        if not is_running:
            raise EnvironmentError(f"{store_cls.s_driver_name}({hostname}) is not running")

        cls.with_auth = with_auth
        if with_auth:
            cls.username  = cls.SIDEKICK_USER
            cls.password = cls.SIDEKICK_USER
        else:
            cls.username = ''
            cls.password = ''

        return store_cls.instance(hostname = hostname, dbname = cls.BACKBONE_DB_NAME, username = cls.username, password = cls.password)

    @classmethod
    @cache
    def store(cls, db_name: str) -> TsStore:
        bb_store = cls.bb_store()
        if db_name == cls.BACKBONE_DB_NAME:
            return bb_store

        return cls.store_cls.instance(hostname = cls.hostname, dbname = db_name, username = cls.username, password = cls.password)
