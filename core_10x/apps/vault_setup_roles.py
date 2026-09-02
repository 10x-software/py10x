"""Install Mongo/Postgres roles and GRANTs for vault collections.

Installed as ``xx-vault-setup-roles``. Requires a database superuser.
See ``docs/USER_ONBOARDING_AUTH.md`` (Part I) and
``docs/VAULT_SECURITY_DESIGN.md`` §3.4.
"""

from __future__ import annotations

import getpass

from core_10x.environment_variables import EnvVars
from core_10x.rc import RC
from core_10x.trait_definition import RT, T
from core_10x.traitable_cli import TraitableCli
from core_10x.ts_store import TsStore
from core_10x.vault_roles import VaultRoles


class VaultSetupRolesCli(TraitableCli):
    """Create vault collections and xxVaultWorker / xxVaultAdmin DB roles.

    Usage:
      xx-vault-setup-roles
      xx-vault-setup-roles --worker alice
      xx-vault-setup-roles --vault-admin bob
      xx-vault-setup-roles --uri postgresql://host/_vault_ --username postgres

    Do not use ``create_xx_user`` / the stock ``xxUser`` role on the vault.
    """

    uri: str = RT()
    username: str = RT(T.STICKY)
    worker: str = RT('')
    vault_admin: str = RT('')

    def uri_get(self) -> str:
        return EnvVars.main_vault_uri

    def username_get(self):
        return input('Vault database admin login: ')

    def post_verify(self) -> RC:
        rc = super().post_verify()
        if not self.uri:
            return rc + RC(False, 'vault URI is required (XX_MAIN_VAULT_URI or --uri)')
        return rc

    def run(self) -> RC:
        password = getpass.getpass(f"{self.username}'s password for the vault database: ")
        try:
            vault = TsStore.instance_from_uri(
                self.uri, username=self.username or None, password=password or None, _cache=False, _create_if_needed=True
            )
        except Exception as e:  # noqa: BLE001
            return RC(False, f'failed to connect to vault at {self.uri}: {e}')

        worker_password = admin_password = None
        if self.worker and not (worker_password := getpass.getpass(f'password for worker {self.worker!r}: ')):
            return RC(False, 'password is required for --worker')
        if self.vault_admin and not (admin_password := getpass.getpass(f'password for vault admin {self.vault_admin!r}: ')):
            return RC(False, 'password is required for --vault-admin')

        rc = VaultRoles.setup(
            vault,
            worker=self.worker,
            worker_password=worker_password,
            vault_admin=self.vault_admin,
            admin_password=admin_password,
        )
        if rc:
            parts = ['vault worker/admin roles installed']
            if self.worker:
                parts.append(f'worker login {self.worker!r}')
            if self.vault_admin:
                parts.append(f'admin login {self.vault_admin!r}')
            print('; '.join(parts))
        return rc


if __name__ == '__main__':
    raise SystemExit(VaultSetupRolesCli.main())
