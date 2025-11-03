from core_10x.named_constant import NamedConstant


# fmt: off
BACKBONE_STORE_CLASS_NAME   = 'infra_10x.mongo_db.Mongo'
#BACKBONE_USER_NAME         = 'core_10x.backbone.backbone_admin.BACKBONE_USER'

AUTO_PASSWORD_LENGTH        = 32

class DB_NAME:
    ANY         = ''
    NONE        = '_none'
    ADMIN       = 'admin'
    BACKBONE    = '_backbone_'
    VAULT       = '_vault_'
    SHADOW      = '_shadow_'

class STANDARD_ROLE:
    READ            = 'read'
    READ_ANY        = 'readAnyDatabase'
    READ_WRITE      = 'readWrite'
    READ_WRITE_ANY  = 'readWriteAnyDatabase'
    DB_ADMIN        = 'dbAdmin'
    DB_ADMIN_ANY    = 'dbAdminAnyDatabase'
    OWNER           = 'dbOwner'
    USER_ADMIN      = 'userAdmin'
    USER_ADMIN_ANY  = 'userAdminAnyDatabase'
    CLUSTER_ADMIN   = 'clusterAdmin'
    CLUSTER_MAN     = 'clusterManager'
    BACKUP          = 'backup'
    RESTORE         = 'restore'
    ROOT            = 'root'

class ACTION:
    FIND            = 'find'
    INSERT          = 'insert'
    UPDATE          = 'update'
    REMOVE          = 'remove'
    INDEX_LIST      = 'listIndexes'
    INDEX_CREATE    = 'createIndex'
    COLL_LIST       = 'listCollections'
    COLL_STATS      = 'collStats'
    COLL_RENAME     = 'renameCollectionSameDB'
    COLL_CREATE     = 'createCollection'
    COLL_DROP       = 'dropCollection'
    DB_LIST         = 'listDatabases'
    DB_STATS        = 'dbStats'
    CHANGE_STREAME  = 'changeStream'

    CHANGE_OWN_PASSWORD = 'changeOwnPassword'

class PERMISSION:
    NONE        = []
    NEW_PWD     = [ ACTION.CHANGE_OWN_PASSWORD ]
    READ_ONLY   = [ ACTION.FIND ]
    READ_EX     = [ ACTION.FIND, ACTION.COLL_LIST ]
    WRITE       = [ ACTION.INSERT, ACTION.UPDATE, ACTION.REMOVE ]
    INDEX       = [ ACTION.INDEX_LIST, ACTION.INDEX_CREATE ]
    COLL        = [ ACTION.COLL_LIST, ACTION.COLL_RENAME, ACTION.COLL_STATS, ACTION.COLL_CREATE, ACTION.COLL_DROP ]

    UPDATE      = [ *READ_ONLY, ACTION.UPDATE ]
    READ_WRITE  = [ *READ_ONLY, *WRITE, *INDEX, *COLL ]

USER_ADMIN_SUFFIX               = 'admin'
FUNCTIONAL_ACCOUNT_PREFIX       = 'xx'
FUNCTIONAL_ACCOUNT_DEPARTMENT   = 'XX Functional Accounts'

class USER_ROLE(NamedConstant):
    NONE        = []
    VISITOR     = PERMISSION.READ_EX
    WORKER      = PERMISSION.READ_WRITE

class COLL_PLACEHOLDER:
    TAG         = '__coll_placeholder'
    USERNAME    = 'username'
# fmt: on


class CUSTOM_ROLE(NamedConstant):
    """
    role_name: e.g., 'VISITOR'
    permissions_per_db_name: a dict: each key is either a db_name or db_name/collection_name, value is PERMISSION, e.g.,
    { 'catalog': PERMISSION.READ_ONLY, 'logs/errors': PERMISSION.READ_WRITE }
    """

    @classmethod
    def coll_placeholder(cls, value) -> tuple:  # -- (coll_placeholder, stripped_value)
        cvalue = dict(value)
        return (cvalue.pop(COLL_PLACEHOLDER.TAG, None), value)

    @classmethod
    def user_role_name(cls, username: str) -> str:
        return f'{username.upper()}_USR'


# fmt: off
SECURITY_KEYS_MISSING = 'Sec keys are missing. If you are using a new computer, please run "xx user new machine" from your shell'
SECURITY_KEYS_INCOMPATIBLE = 'Sec keys are incompatible with an encrypted password'

SECRETS_CLIENT_ARGS     = dict(service_name = 'secretmanager', region_name = 'me-south-1')
SECRETS_PATH_PREFIX     = '/external-secrets/xx'
# fmt: on
