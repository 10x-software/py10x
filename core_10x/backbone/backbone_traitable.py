from core_10x.backbone.backbone_store import BackboneStore
from core_10x.traitable import RC, RT, T, Traitable, TraitDefinition  # noqa: F401
from core_10x.ts_store import TsStore


class BackboneTraitable(Traitable):
    @staticmethod
    def build_trait_dir(bases, class_dict, trait_dir) -> RC:
        for trait_def in class_dict.values():
            if isinstance(trait_def, TraitDefinition):
                trait_def.flags_change(T.EVAL_ONCE)

        return Traitable.build_trait_dir(bases, class_dict, trait_dir)

    @classmethod
    def store(cls) -> TsStore:
        return BackboneStore.bb_store()


class VaultTraitable(BackboneTraitable):
    @classmethod
    def store(cls) -> TsStore:
        return BackboneStore.store(BackboneStore.VAULT_DB_NAME)
