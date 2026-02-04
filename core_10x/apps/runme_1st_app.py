from core_10x.environment_variables import EnvVars
from core_10x.ts_store import TsStore

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
1) Main Traitable Store is specified (Environment variable {EnvVars.var_name(v_main_uri.attr_name)} = {v_main_uri.value})
It means that Traitable objects would be sought and saved in the above store.  
"""
    )
    v_class_assoc = EnvVars.var.use_ts_store_per_class
    if v_class_assoc:
        print(
f"""
2) Different Traitable Stores may be used for different subclasses of Traitable (Environment variable {EnvVars.var_name(v_class_assoc.attr_name)} = {v_class_assoc.value})
Checking further...
"""
        )



if __name__ == '__main__':

    import sys

    main(*sys.argv[1:])

