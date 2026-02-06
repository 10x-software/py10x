from core_10x.traitable import VaultUser, TsStore
from core_10x.sec_keys import SecKeys

class VaultUtils:
    @classmethod
    def create_user(cls, master_password: str, save = True) -> VaultUser:
        SecKeys.change_master_password(master_password)
        private_key_pem, public_key_pem = SecKeys.generate_keys()
        me = VaultUser()
        me.public_key = public_key_pem
        me.private_key_encrypted = SecKeys.encrypt_private_key(private_key_pem, master_password)

        if save:
            me.save().throw()

        return me

    @classmethod
    def new_vault(cls, vault_uri: str, password: str, master_password: str = None):
        username = VaultUser.myname()
        vault_db = TsStore.instance_from_uri(vault_uri, username = username, password = password)
        with vault_db:
            me = VaultUser.existing_instance(user_id = username, _throw = False)
            if not me:
                if not master_password:
                    raise AssertionError('Master password is required')
                me = cls.create_user(master_password)
            else:
                existing_master_password = SecKeys.retrieve_master_password(throw = False)
                if not existing_master_password:
                    raise AssertionError('No existing MasterPassword found')
                if existing_master_password != master_password:
                    raise AssertionError('MasterPassword provided does not match the stored one')

            SecKeys.change_vault_password(vault_uri, password)
