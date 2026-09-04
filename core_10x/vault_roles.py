"""Install worker/admin privileges on vault collections.

Stock ``xxUser`` (``infra_10x.mongodb_utils.create_xx_user``) is ``anyResource``
read/write and must not be used on the vault. See
``docs/VAULT_SECURITY_DESIGN.md`` §3.4.

Mongo/Postgres GRANTs live on ``TsStore.setup_vault_roles`` /
``create_vault_user`` / ``create_vault_admin``.
"""

from __future__ import annotations

from core_10x.package_refactoring import PackageRefactoring
from core_10x.rc import RC, RC_TRUE
from core_10x.traitable import TraitableHistory, VaultResourceAccessor, VaultUser
from core_10x.ts_store import TsStore


class VaultRoles:
    """Create vault collections and the worker/admin DB roles. Superuser connection."""

    WORKER_ROLE = TsStore.VAULT_WORKER_ROLE
    ADMIN_ROLE = TsStore.VAULT_ADMIN_ROLE
    _VAULT_CLASSES = (VaultUser, VaultResourceAccessor)

    @staticmethod
    def _class_collection_name(traitable_cls) -> str:
        return PackageRefactoring.find_class_id(traitable_cls)

    @classmethod
    def vault_collection_names(cls) -> tuple[str, ...]:
        names: list[str] = []
        for tcls in cls._VAULT_CLASSES:
            cname = cls._class_collection_name(tcls)
            names.append(cname)
            names.append(TraitableHistory.history_collection_name(cname))
        return tuple(names)

    @classmethod
    def setup(
        cls,
        store: TsStore,
        *,
        worker: str = '',
        worker_password: str | None = None,
        vault_admin: str = '',
        admin_password: str | None = None,
        worker_role: str | None = None,
        admin_role: str | None = None,
    ) -> RC:
        worker_role = worker_role or cls.WORKER_ROLE
        admin_role = admin_role or cls.ADMIN_ROLE
        if not store.can_serve_as_vault():
            return RC(False, f'{type(store).__name__} cannot serve as a vault')

        rc = cls.ensure_schema(store)
        if not rc:
            return rc
        vu = cls._class_collection_name(VaultUser)
        vra = cls._class_collection_name(VaultResourceAccessor)
        rc = store.setup_vault_roles(
            user_collection=vu,
            user_history=TraitableHistory.history_collection_name(vu),
            accessor_collection=vra,
            accessor_history=TraitableHistory.history_collection_name(vra),
            worker_role=worker_role,
            admin_role=admin_role,
        )
        if rc and worker:
            rc = store.create_vault_user(worker, worker_password or '', worker_role=worker_role, admin_role=admin_role)
        if rc and vault_admin:
            rc = store.create_vault_admin(vault_admin, admin_password or '', worker_role=worker_role, admin_role=admin_role)
        return rc

    @classmethod
    def ensure_schema(cls, store: TsStore) -> RC:
        """Create vault tables/collections and indexes so workers never DDL."""
        try:
            with store:
                for tcls in cls._VAULT_CLASSES:
                    tcls.collection(create_if_needed=True)
                    if tcls.s_history_class is not None:
                        tcls.s_history_class.collection(create_if_needed=True)
        except Exception as e:  # noqa: BLE001
            return RC(False, f'vault schema setup failed: {e}')
        return RC_TRUE
