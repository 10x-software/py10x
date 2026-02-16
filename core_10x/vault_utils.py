import getpass

from core_10x.traitable import VaultUser, VaultResourceAccessor, Resource, TsStore, RC, RC_TRUE
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
    def create_master_password(cls, ovveride = False) -> RC:
        if not ovveride:
            mp = SecKeys.retrieve_master_password(throw = False)
            if mp is not None:
                return RC(False, 'MasterPassword already exists')

        mp = getpass.getpass('Please create a memorable MasterPassword: ')
        mp2= getpass.getpass('Please re-enter your MasterPassword: ')
        rc = cls.verify_new_password(mp, mp2)
        if rc:
            SecKeys.change_master_password(mp, override = True)

        return rc

    @classmethod
    def change_master_password(cls) -> RC:
        old_mp = SecKeys.retrieve_master_password(throw = False)
        if old_mp is not None:
            proceed = input('Are you sure you want to override your existing MasterPassword? [y/n]')
            if proceed.upper() != 'Y':
                return RC_TRUE

        return cls.create_master_password(ovveride = True)

    @classmethod
    def _create_user(cls, save = True) -> VaultUser:  #-- must be called inside with vault_store block
        private_key_pem, public_key_pem = SecKeys.generate_keys()
        master_password = SecKeys.retrieve_master_password()
        me = VaultUser(
            _replace                = True,
            public_key              = public_key_pem,
            private_key_encrypted   = SecKeys.encrypt_private_key(private_key_pem, master_password),
        )
        if save:
            me.save().throw()

        return me

    @classmethod
    def get_vault(cls, vault_uri: str = None) -> TsStore:
        if vault_uri is None:
            vault_uri = input('Please enter vault URI: ')

        vault_password = SecKeys.retrieve_vault_password(vault_uri = vault_uri, throw = False)
        if not vault_password:
            vault_password = getpass.getpass('Please enter password for the vault: ')

        return TsStore.instance_from_uri(vault_uri, username = VaultUser.myname(), password = vault_password)

    @classmethod
    def register_vault(cls) -> RC:
        if not SecKeys.retrieve_master_password(throw = False):
            rc = cls.create_master_password()
            if not rc:
                return rc

        vault_uri = input('Please enter vault URI (e.g., mongodb://vaultdb.xxx.io[:27017]/vault): ')
        password = getpass.getpass('Please enter password for the vault (should have been given to you by admin): ')

        username = VaultUser.myname()
        vault_db = TsStore.instance_from_uri(vault_uri, username = username, password = password)

        with vault_db:
            if not VaultUser.existing_instance(user_id = username, _throw = False):
                cls._create_user()

        SecKeys.change_vault_password(password, vault_uri = vault_uri, override = True)
        return RC_TRUE

    @classmethod
    def enter_resource_accessors(cls) -> RC:
        vault_db = cls.get_vault()
        with vault_db:
            while True:
                user_id = input('Please enter user ID the resource accessors are for: ')
                if not user_id:
                    break

                vault_user = VaultUser.existing_instance(user_id = user_id, _throw = False)
                if not vault_user:
                    print(f"User '{user_id}' has not registered yet. Please inform '{user_id}'")
                    continue

                while True:
                    uri = input('Please enter resource URI: ')
                    if not uri:
                        break

                    while True:
                        login = input(f"Please enter login name for'{user_id}': ")
                        if not login:
                            break

                        password = getpass.getpass(f"Please enter password for '{login}': ")
                        if not password:
                            continue

                        try:
                            Resource.instance_from_uri(uri, username = login, password = password)
                        except Exception as ex:
                            print(f'{str(ex)}')

                        VaultResourceAccessor.save_ra(uri, password, login = login, username = user_id)

