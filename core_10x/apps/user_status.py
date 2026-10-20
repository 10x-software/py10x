"""User-facing status check for vault and resource-accessor setup.

Installed by ``py10x-core`` as the ``xx-user-status`` console script (see
``pyproject.toml``); also runnable directly as
``python -m core_10x.apps.user_status``.
"""

from __future__ import annotations

from core_10x.rc import RC, exc_to_rc
from core_10x.sec_keys import SecKeys
from core_10x.trait_definition import RT, T
from core_10x.trait_filter import f
from core_10x.traitable import Traitable, VaultResourceAccessor, VaultUser
from core_10x.traitable_cli import TraitableCli
from core_10x.ts_store import TsStore


def _keyring_setup_hint(vault_uri: str) -> str:
    """Best-effort hint: prefer ``--new-machine`` when a VaultUser row already exists."""
    rc, login, password = SecKeys.retrieve_vault_login_password(vault_uri)
    if rc:
        try:
            vault = TsStore.instance_from_uri(vault_uri, username=login, password=password, _cache=False)
            with vault:
                if VaultUser.existing_instance(_throw=False):
                    return 'run: xx-user-init --new-machine'
        except Exception:  # noqa: S110 - best-effort hint; any failure falls through to the generic message
            pass
    return 'run: xx-user-init --new-user  (first machine) or xx-user-init --new-machine  (existing account on a new machine)'


class UserStatusCli(TraitableCli):
    """Check vault and resource-accessor setup for the current OS user.

    Usage:
      xx-user-status
    """

    vault_uri: str = RT()
    vault_user_id: str = RT(T.STICKY)
    resource_accessors: list = RT(T.STICKY)

    def vault_uri_get(self) -> str:
        return SecKeys.check_vault_uri(main=True)[1]

    def vault_user_id_get(self) -> str:
        with Traitable.vault_store():
            if me := VaultUser.existing_instance(_throw=False):
                return me.user_id
        return ''

    def resource_accessors_get(self) -> list:
        with Traitable.vault_store():
            return VaultResourceAccessor.load_many(f(username=VaultUser.myname()))

    @exc_to_rc
    def check_os_login(self) -> None:
        os_login = VaultUser.myname()
        print(f'[0] OS login (vault account name) = {os_login!r}')
        print('    Use this exact string for the vault-DB login (--worker).')
        print('    Send it to your DBA / vault admin if they do not already know it')

    @exc_to_rc(show_exception_info=False)
    def check_vault_uri(self) -> None:
        rc, vault_uri = SecKeys.check_vault_uri(main=True)
        if not rc:
            raise RuntimeError('[1] XX_MAIN_VAULT_URI is not set -- set: export XX_MAIN_VAULT_URI=mongodb://<host>:<port>/<db>')
        print(f'[1] Vault URI = {vault_uri}')

    @exc_to_rc(show_exception_info=False)
    def check_master_password(self) -> None:
        if not SecKeys.retrieve_master_password()[0]:
            raise RuntimeError(
                f'[2] Master password not found in OS keyring -- this machine is not set up for vault access -- {_keyring_setup_hint(self.vault_uri)}'
            )
        print('[2] Master password (OS keyring): found')

    @exc_to_rc(show_exception_info=False)
    def check_vault_login(self) -> None:
        rc, login = SecKeys.retrieve_vault_login_password(self.vault_uri)[:2]
        if not rc:
            raise RuntimeError(
                f'[3] Vault login/password not found in OS keyring -- this machine is not set up for vault access -- {_keyring_setup_hint(self.vault_uri)}'
            )
        print(f'[3] Vault login/password (OS keyring): login = {login!r}')

    @exc_to_rc
    def check_vault_connection(self) -> None:
        if not (vault_user_id := self.vault_user_id):
            raise RuntimeError(
                f'[4] No user record found for {VaultUser.myname()!r} in the vault -- '
                f'XX_MAIN_VAULT_URI may be pointing to the wrong vault (currently: {self.vault_uri})'
            )
        print(f'[4] Vault connection and user record: user_id = {vault_user_id!r}')

    @exc_to_rc(show_exception_info=False)
    def check_resource_accessors(self) -> None:
        print('[5] Resource accessors')
        if not self.resource_accessors:
            print('    (none registered -- run xx-user-save-credentials, or ask an admin to run xx-admin-save-user-credentials)')
            return
        failures = []
        for ra in self.resource_accessors:
            label = f'{ra.resource_dt.name}  {ra.resource_uri}  (login: {ra.login})'
            try:
                ra.resource  # noqa: B018 useless-expression
                print(f'    OK    {label}')
            except Exception as exc:
                print(f'    FAIL  {label}: {exc}')
                failures.append(label)
        if failures:
            raise RuntimeError(
                f'resource accessor(s) failed to connect: {", ".join(failures)} -- '
                'check that the server is reachable and ask an admin to verify or refresh the stored credentials'
            )

    def run(self) -> RC:
        rc = self.check_os_login() + self.check_vault_uri()
        if not rc:
            return rc  # nothing else makes sense without a vault URI

        rc += self.check_master_password() + self.check_vault_login()
        if not rc:
            return rc  # can't reach the vault without vault credentials

        rc += self.check_vault_connection()
        if not rc:
            return rc  # can't get resource accessors without vault connection

        rc += self.check_resource_accessors()

        print()
        print('All checks passed.' if rc else 'One or more checks failed -- see errors above.')
        return rc


if __name__ == '__main__':
    raise SystemExit(UserStatusCli.main())
