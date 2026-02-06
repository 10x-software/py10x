from __future__ import annotations

from py10x_core import OsUser

from core_10x.attic.backbone.backbone_traitable import RT, BackboneTraitable, T
from core_10x.attic.backbone.namespace import FUNCTIONAL_ACCOUNT_PREFIX, USER_ADMIN_SUFFIX
from core_10x.global_cache import cache
from core_10x.trait_filter import f


class BackboneUserGroup(BackboneTraitable):
    # fmt: off
    name: str           = T(T.ID)
    description: str    = T()
    everyone: bool      = T(False)
    is_admin: bool      = T(False)
    is_reserved: bool   = T(False)
    builtin_roles: list = T()
    user_ids: list      = T()

    users: set          = RT()
    # fmt: on

    def users_get(self) -> set:
        return set(self.user_ids)

    def is_member(self, user_id: str) -> bool:
        return user_id in self.users if not self.everyone else False


class BackboneUser(BackboneTraitable):
    # fmt: off
    user_id: str        = T(T.ID)   // 'OS login'
    suspended: bool     = T(False)
    public_key: bytes   = T()

    is_admin: bool      = RT()
    downloaded: bool    = RT(False)
    builtin_roles: list = RT()
    # fmt: on

    def user_id_get(self) -> str:
        return OsUser.me.name()

    def is_admin_get(self) -> bool:
        for group in BackboneUserGroup.collection().find(f(is_admin=True)):
            if group.is_member(self.user_id):
                return True

        return False

    def admin_id(self) -> str:
        return f'{self.user_id}_{USER_ADMIN_SUFFIX}' if self.is_admin else ''

    @classmethod
    def regular_id(cls, admin_id: str) -> str:
        return admin_id.split(f'_{USER_ADMIN_SUFFIX}')[0]

    @classmethod
    def is_functional_account(cls, user_id: str) -> bool:
        return user_id.split('-', 1) == FUNCTIONAL_ACCOUNT_PREFIX

    @classmethod
    @cache
    def me(cls) -> BackboneUser:
        return cls.existing_instance(user_id=OsUser.me.name())
