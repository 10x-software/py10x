from core_10x.environment_variables import EnvVars

from core_10x.ts_store import TsStore, ResourceSpec
from core_10x.traitable import NamedTsStore, TsClassAssociation


def main(username: str = '', password: str = ''):
    v_main_uri: EnvVars.Var = EnvVars.var.main_ts_store_uri
    if not v_main_uri:
        print(
f"""
Environment variable {EnvVars.var_name(v_main_uri.attr_name)} is not defined
Main Traitable Store is not specified, thus you must explicitly instantiate and use a particular Traitable Store, e.g.:

    with TsStore.instance_from_uri('mongodb://public_mongo_host.abc.com/test'):     #-- no authentication
        # your code
        ...
        
    or

    #-- Authentication is required
    password = 'a VeryStrongPassword!'
    with TsStore.instance_from_uri('mongodb://protected_mongo_host.abc.com/test', username = 'xyz', password = password):
        # your code
        ...
"""
        )
        #-- there is nothing more to do
        return

    print(
f"""
Main Traitable Store is specified (Environment variable {EnvVars.var_name(v_main_uri.attr_name)} = {v_main_uri.value})
It means that Traitable objects would be sought and saved in the above store.  
"""
    )

    main_spec = TsStore.spec_from_uri(v_main_uri.value)
    is_running, with_auth = main_spec.resource_class.is_running_with_auth(main_spec.hostname())
    if not is_running:
        print(f'Main Traitable Store {v_main_uri.value} is not running')
        return

    if with_auth:
        print(f"Main Traitable Store {v_main_uri.value} requires authentication. Let's check if a Vault is specified." )

        v_vault_uri = EnvVars.var.vault_ts_store_uri
        if not v_vault_uri:
            print(f"No Vault is specified (Environment variable {EnvVars.var_name(v_vault_uri.attr_name)} is not defined). Exiting...")
            return

        print(
f"""
Vault Store is specified (Environment variable {EnvVars.var_name(v_vault_uri.attr_name)} = {v_vault_uri.value})
It means that some Traitable Stores in use (as well as other resources) require authentication.
In order to use the Vault "automagically", you need to run "add_vault utiliry" entering your password to the Vault and your XX MasterPassword.
"""
        )
        return

    main_store = main_spec.resource_class.instance(**main_spec.kwargs)
    v_class_assoc = EnvVars.var.use_ts_store_per_class
    if v_class_assoc:
        print(
f"""
Different Traitable Stores may be used for different subclasses of Traitable (Environment variable {EnvVars.var_name(v_class_assoc.attr_name)} = {v_class_assoc.value})
Checking further...
"""
        )

        main_store.begin_using()

        available_stores = NamedTsStore.load_many()


if __name__ == '__main__':

    import sys

    main(*sys.argv[1:])

