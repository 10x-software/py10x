import getpass

from core_10x.environment_variables import EnvVars
from core_10x.traitable import Traitable, VaultUser, VaultResourceAccessor, Resource, TsStore, RC, RC_TRUE
from core_10x.concrete_resource import CONCRETE_RESOURCE
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
            rc.add_error('password must have at least one letter')
        if not any(c.isupper() for c in pwd):
            rc.add_error('password must have at least one capital letter')
        if not any(c.isdigit() for c in pwd):
            rc.add_error('password must have at least one digit')
        if pwd != pwd2:
            rc.add_error('passwords do not match')

        if not rc:
            rc.prepend_error_header('New password cannot be used:')

        return rc

    @classmethod
    def create_master_password(cls, ovveride = False) -> tuple[RC, str]:
        if not ovveride:
            rc, mp = SecKeys.retrieve_master_password()
            if rc:
                return (RC(False, 'MasterPassword already exists'), None)

        mp = getpass.getpass('Please create a memorable MasterPassword: ')
        mp2= getpass.getpass('Please re-enter your MasterPassword: ')
        rc = cls.verify_new_password(mp, mp2)
        if not rc:
            return (rc, None)

        SecKeys.change_master_password(mp, override = True)
        return (RC_TRUE, mp)

    @classmethod
    def change_master_password(cls) -> tuple[RC, str]:
        rc, old_mp = SecKeys.retrieve_master_password()
        if rc:
            proceed = input('Are you sure you want to override your existing MasterPassword? [y/n]')
            if proceed.lower() != 'y':
                return (RC_TRUE, None)

        return cls.create_master_password(ovveride = True)

    @classmethod
    def get_vault(cls, vault_uri: str = None) -> TsStore:
        if not vault_uri:
            vault_uri = EnvVars.vault_uri
            if not vault_uri:
                vault_uri = input('Please enter vault URI: ')

        rc, login, password = SecKeys.retrieve_vault_login_password(vault_uri)
        if not rc:
            raise OSError(f'Unknown vault {vault_uri}.\nPlease run vault_init utility')

        return TsStore.instance_from_uri(vault_uri, username = login, password = password)

    @classmethod
    def user_init(cls) -> RC:
        rc, vault_uri = SecKeys.check_vault_uri(main = True)
        if not rc:
            return rc

        rc, login, password = SecKeys.retrieve_vault_login_password(vault_uri)
        if rc:
            return rc

        #-- 1. Get main vault credentials and try to connect
        rc, vault, login, password = cls._get_and_check_vault_credentials(vault_uri)
        if not rc:
            return rc

        #-- 2. At this point, connected to the vault, let's create the user object
        username = VaultUser.myname()
        with vault:
            if VaultUser.existing_instance(user_id = username, _throw = False):
                return RC(False, f'Vault User {username} already exists. Consult with admin')

            #cls._create_user()
            rc, master_pwd = cls.create_master_password(ovveride = True)
            if not rc:
                raise OSError(rc.error())

            me = VaultUser()
            private_key_pem, public_key_pem = SecKeys.generate_keys()
            me.set_values(
                public_key              = public_key_pem,
                private_key_encrypted   = SecKeys.encrypt_private_key(private_key_pem, master_pwd),
            ).throw()
            me.save().throw()

        #-- 3. Store login/password for the main vault
        SecKeys.change_vault_login_password(login, password, vault_uri = vault_uri, override = True)
        return RC_TRUE

    @classmethod
    def _get_and_check_vault_credentials(cls, vault_uri: str) -> tuple[RC, TsStore, str, str]:
        username = VaultUser.myname()
        login = input(f'Enter login name for {vault_uri} ({username}): ')
        if not login:
            login = username
        password = getpass.getpass(f'Enter password (given to you by admin) for {login} @ {vault_uri} : ')
        try:
            vault = TsStore.instance_from_uri(vault_uri, username = login, password = password, _cache = False)
            return (RC_TRUE, vault, login, password)

        except Exception:
            return (RC(False, f'Failed to connect to {login} @ {vault_uri}'), None, None, None)


    @classmethod
    def vault_init(cls, vault_uri: str) -> RC:
        try:
            if cls.get_vault(vault_uri):
                return RC_TRUE
        except OSError:
            pass

        if vault_uri == EnvVars.main_vault_uri:
            return cls.user_init()

        rc, main_uri = SecKeys.check_vault_uri(main = True)
        if not rc:
            return rc

        main_vault = cls.get_vault(main_uri)
        with main_vault:
            user = VaultUser.existing_instance(_throw = False)

        if not user:
            return RC(False, 'You must first run user_init utility')

        rc, vault, login, password = cls._get_and_check_vault_credentials(vault_uri)
        if not rc:
            return rc

        SecKeys.change_vault_login_password(login, password, vault_uri = vault_uri, override = True)
        return RC_TRUE

    @classmethod
    def admin_save_user_credentials(cls) -> RC:
        try:
            vault = Traitable.vault_store()
        except Exception as ex:
            rc = RC(False, f'You have no access to the vault. Run vault_init and/or user_init utility')
            rc.add_error(str(ex))
            return rc

        username = input('Enter the user ID: ')
        with vault:
            user = VaultUser.existing_instance(user_id = username, _throw = False)
            if not user:
                return RC(False, f'Vault User {username} does not exist. Ask {username} to run user_init utility')

        res_choices = tuple(f'{name}: {i}' for i, name in enumerate(CONCRETE_RESOURCE.all_names()))
        res_index = int(input(f"Choose CONCRETE_RESOURCE ({', '.join(res_choices)})"))
        resource_dt = CONCRETE_RESOURCE.item(CONCRETE_RESOURCE.all_names()[res_index])
        uri = input(f'Enter URI for {resource_dt}: ')
        login = input(f'Enter login name ({username}): ')
        if not login:
            login = username
        password = getpass.getpass(f'Enter password for {login}: ')

        try:
            resource_dt.value.instance_from_uri(uri, username = login, password = password, _cache = False)
        except Exception as ex:
            rc = RC(False, f'Failed to connect to {login} @ {uri}')
            rc.add_error(str(ex))
            return rc

        with vault:
            return VaultResourceAccessor.save_ra(resource_dt, uri, password, login = login, username = username)


    # @classmethod
    # def enter_resource_accessors(cls) -> RC:
    #     vault_db = cls.get_vault()
    #     with vault_db:
    #         while True:
    #             user_id = input('Please enter user ID the resource accessors are for: ')
    #             if not user_id:
    #                 break
    #
    #             vault_user = VaultUser.existing_instance(user_id = user_id, _throw = False)
    #             if not vault_user:
    #                 print(f"User '{user_id}' has not registered yet. Please inform '{user_id}'")
    #                 continue
    #
    #             while True:
    #                 uri = input('Please enter resource URI: ')
    #                 if not uri:
    #                     break
    #
    #                 while True:
    #                     login = input(f"Please enter login name for'{user_id}': ")
    #                     if not login:
    #                         break
    #
    #                     password = getpass.getpass(f"Please enter password for '{login}': ")
    #                     if not password:
    #                         continue
    #
    #                     try:
    #                         Resource.instance_from_uri(uri, username = login, password = password)
    #                     except Exception as ex:
    #                         print(f'{ex!s}')
    #
    #                     VaultResourceAccessor.save_ra(uri, password, login = login, username = user_id)
    #
