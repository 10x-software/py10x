from __future__ import annotations

from typing import TYPE_CHECKING

from core_10x.attic.backbone.backbone_store import BackboneStore
from core_10x.traitable import T, Traitable, TraitDefinition

if TYPE_CHECKING:
    from core_10x.traitable import RC
    from core_10x.ts_store import TsStore


class BackboneTraitable(Traitable):
    @classmethod
    def build_trait_dir(cls) -> RC:
        for trait_def in cls.__dict__.values():
            if isinstance(trait_def, TraitDefinition):
                trait_def.flags_change(T.EVAL_ONCE)

        return Traitable.build_trait_dir()

    @classmethod
    def store(cls) -> TsStore:
        return BackboneStore.bb_store()


class VaultTraitable(BackboneTraitable):
    @classmethod
    def store(cls) -> TsStore:
        return BackboneStore.store(BackboneStore.VAULT_DB_NAME)
