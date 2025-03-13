from core_10x_i import OsUser

from core_10x.environment_variables import EnvVars
from core_10x.rc import RC
from core_10x.traitable import Traitable, T, RT, TraitDefinition
from core_10x.ts_store import TsStore

class BackboneStore(Traitable):
    user_name: str  = RT()
    password: str   = RT('')

    store: TsStore  = RT()

    def user_name_get(self) -> str:
        return OsUser.me.name()

    def store_get(self) -> TsStore:
        cls_name = EnvVars.backbone_store_class_name
        store_cls = TsStore.store_class(cls_name)
        hostname = EnvVars.backbone_store_host_name

        uname = self.user_name
        pwd = self.password
        username = uname if pwd else ''
        return store_cls.instance(hostname = hostname, dbname = '_backbone', username = username, password = pwd)

class BackboneTraitable(Traitable):
    @staticmethod
    def build_trait_dir(bases, class_dict, trait_dir) -> RC:
        for trait_name, trait_def in class_dict.items():
            if isinstance(trait_def, TraitDefinition):
                trait_def.flags_change(T.EVAL_ONCE)

        return Traitable.build_trait_dir(bases, class_dict, trait_dir)

    @classmethod
    def store(cls) -> TsStore:
        return BackboneStore().store    #-- TODO: add credentials
