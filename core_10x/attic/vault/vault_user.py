from core_10x.environment_variables import EnvVars
from core_10x.ts_store import TsStore
from core_10x.attic.vault.vault_traitable import VaultTraitable, T, RT, OsUser, cache
from core_10x.attic.vault.sec_keys import SecKeys

class VaultUser(VaultTraitable):
    # fmt: off
    user_id: str                    = T(T.ID)   // 'OS login'
    suspended: bool                 = T(False)

    private_key_encrypted: bytes    = T()
    public_key: bytes               = T()

    sec_keys: SecKeys               = RT(T.EVAL_ONCE)
    # fmt: on

    def user_id_get(self) -> str:
        return self.__class__.myname()

    def sec_keys_get(self) -> SecKeys:
        return SecKeys(self.private_key_encrypted, self.public_key, VaultTraitable.retrieve_master_password())

    @classmethod
    def create_new(cls, master_password: str, save = True) -> 'VaultUser':
        VaultTraitable.keep_master_password(master_password)
        private_key_pem, public_key_pem = SecKeys.generate_keys()
        me = VaultUser()
        me.public_key = public_key_pem
        me.private_key_encrypted = SecKeys.encrypt_private_key(private_key_pem, master_password)

        if save:
            me.save().throw()

        return me

    @classmethod
    def new_vault(cls, vault_uri: str, password: str, master_password: str = None):
        username = cls.myname()
        vault_db = TsStore.instance_from_uri(vault_uri, username = username, password = password)
        with vault_db:
            me = cls.existing_instance(user_id = username, _throw = False)
            if not me:
                if not master_password:
                    raise AssertionError('Master password is required')
                me = cls.create_new(master_password)
            else:
                try:
                    existing_master_password = cls.retrieve_master_password()
                except Exception:
                    existing_master_password = None
                if not existing_master_password:
                    raise AssertionError('No existing MasterPassword found')
                if existing_master_password != master_password:
                    raise AssertionError('MasterPassword provided does not match the stored one')

            cls.keep_vault_password(vault_uri, password)

    @classmethod
    def is_functional_account(cls, user_id: str) -> bool:
        return user_id.split('-', 1) == EnvVars.functional_account_prefix

    @classmethod
    @cache
    def myname(cls) -> str:
        return OsUser.me.name()

    @classmethod
    @cache
    def me(cls) -> 'VaultUser':
        return cls.existing_instance(user_id=cls.myname())
