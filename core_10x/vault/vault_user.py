import keyring

from core_10x.vault.vault_traitable import VaultTraitable, T, RT, OsUser, cache, EnvVars
from core_10x.vault.sec_keys import SecKeys

"""
user = 'admin'
db2 = TsStore.instance_from_uri(f'mongodb://{user}:{keyring.get_password("mongodb_local", user)}@localhost:27018/test')
"""

class VaultUser(VaultTraitable):
    FUNCTIONAL_ACCOUNT_PREFIX = 'xx'

    # fmt: off
    user_id: str                    = T(T.ID)   // 'OS login'
    suspended: bool                 = T(False)

    private_key_encrypted: bytes    = T()
    public_key: bytes               = T()

    sec_keys: SecKeys               = RT(T.EVAL_ONCE)
    # fmt: on

    def user_id_get(self) -> str:
        return OsUser.me.name()

    def sec_keys_get(self) -> SecKeys:
        return SecKeys(self.private_key_encrypted, self.public_key, self.master_password())

    #-- TODO: what about resetting ALL the resource accessors in Vault?
    def set_master_password(self, pwd: str):
        keyring.set_password(EnvVars.master_password_key, self.user_id, pwd)
        private_key_pem, public_key_pem = SecKeys.generate_keys()
        self.public_key = public_key_pem
        self.private_key_encrypted = SecKeys.encrypt_private_key(private_key_pem, pwd)

        self.save().throw()

    @classmethod
    def is_functional_account(cls, user_id: str) -> bool:
        return user_id.split('-', 1) == cls.FUNCTIONAL_ACCOUNT_PREFIX

    @classmethod
    @cache
    def me(cls) -> 'VaultUser':
        return cls.existing_instance(user_id=OsUser.me.name())
