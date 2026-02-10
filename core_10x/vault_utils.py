import getpass

from core_10x.traitable import VaultUser, TsStore, RC
from core_10x.sec_keys import SecKeys

class VaultUtils:
    MIN_CHARS   = 8
    @classmethod
    def verify_new_password(cls, pwd: str, pwd2: str) -> RC:
        rc = RC(True)
        if not pwd or not pwd2:
            rc.add_error('passwords must not be empty')
        n = len(pwd)
        if n < cls.MIN_CHARS:
            rc.add_error(f'password must be at least {cls.MIN_CHARS} characters long')
        if not any(c.isalpha() for c in pwd):
            rc.add_error(f'password must have at least one letter')
        if not any(c.isupper() for c in pwd):
            rc.add_error(f'password must have at least one capital letter')
        if not any(c.isdigit() for c in pwd):
            rc.add_error(f'password must have at least one digit')
        if pwd != pwd2:
            rc.add_error(f'passwords do not match')

        if not rc:
            rc.prepend_error_header('New password cannot be used:')

        return rc

    @classmethod
    def _create_user(cls, master_password: str, repeat_master_password: str, save = True) -> VaultUser:  #-- must be called inside with vault_store block
        cls.verify_new_password(master_password, repeat_master_password).throw()
        SecKeys.change_master_password(master_password)
        private_key_pem, public_key_pem = SecKeys.generate_keys()
        me = VaultUser(
            _replace                = True,
            public_key              = public_key_pem,
            private_key_encrypted   = SecKeys.encrypt_private_key(private_key_pem, master_password),
        )
        if save:
            me.save().throw()

        return me

    # @classmethod
    # def new_vault(cls, vault_uri: str, password: str, master_password: str, repeat_master_password: str = None):
    #     username = VaultUser.myname()
    #     vault_db = TsStore.instance_from_uri(vault_uri, username = username, password = password)
    #     with vault_db:
    #         me = VaultUser.existing_instance(user_id = username, _throw = False)
    #         if not me:
    #             cls._create_user(master_password, repeat_master_password)
    #         else:   #-- user exists
    #             existing_master_password = SecKeys.retrieve_master_password(throw = False)
    #             if not existing_master_password:
    #                 raise AssertionError(f'{username}: no existing MasterPassword found')
    #             if existing_master_password != master_password:
    #                 raise AssertionError(f'{username}: MasterPassword provided does not match the stored one')
    #
    #         SecKeys.change_vault_password(password, vault_uri = vault_uri, override = True)

    @classmethod
    def new_vault(cls):
        vault_uri = input('Please enter a new vault URI (e.g., mongodb://vaultdb.xxx.io[:27017]/vault): ')
        password = getpass.getpass('Please enter password for the vault (should be given to you by the admin): ')

        username = VaultUser.myname()
        vault_db = TsStore.instance_from_uri(vault_uri, username = username, password = password)
        master_password = getpass.getpass('Please enter your MasterPassword: ')
        with vault_db:
            me = VaultUser.existing_instance(user_id = username, _throw = False)
            if not me:
                master_password2 = getpass.getpass('Please re-enter your MasterPassword: ')
                cls._create_user(master_password, master_password2)
            else:   #-- user exists
                existing_master_password = SecKeys.retrieve_master_password(throw = False)
                if not existing_master_password:
                    raise AssertionError(f'{username}: no existing MasterPassword found')
                if existing_master_password != master_password:
                    raise AssertionError(f'{username}: MasterPassword provided does not match the stored one')

            SecKeys.change_vault_password(password, vault_uri = vault_uri, override = True)
