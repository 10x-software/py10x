"""User-facing status check for vault and resource-accessor setup.

Installed by ``py10x-core`` as the ``xx-user-status`` console script (see
``pyproject.toml``); also runnable directly as
``python -m core_10x.apps.user_status``.

Exit codes:
  0 — all checks passed
  1 — one or more checks failed (section [0] OS login is always printed)
"""

from __future__ import annotations


def _keyring_setup_hint(vault_uri: str) -> str:
    """Best-effort hint: prefer ``--new-machine`` when a VaultUser row already exists."""
    from core_10x.sec_keys import SecKeys

    rc, login, password = SecKeys.retrieve_vault_login_password(vault_uri)
    if rc:
        try:
            from core_10x.traitable import TsStore, VaultUser

            vault = TsStore.instance_from_uri(vault_uri, username=login, password=password, _cache=False)
            with vault:
                if VaultUser.existing_instance(_throw=False):
                    return 'run: xx-user-init --new-machine'
        except Exception:  # noqa: S110 - best-effort hint; any failure falls through to the generic message
            pass
    return 'run: xx-user-init --new-user  (first machine) or xx-user-init --new-machine  (existing account on a new machine)'


def main() -> int:
    ok = True

    def _ok(msg: str) -> None:
        print(f'  OK  {msg}')

    def _fail(msg: str, hint: str = '') -> None:
        nonlocal ok
        ok = False
        print(f'FAIL  {msg}')
        if hint:
            print(f'      hint: {hint}')

    # ------------------------------------------------------------------
    # 0. OS login — always shown (needed before vault account creation)
    # ------------------------------------------------------------------
    print('\n[0] OS login (vault account name)')
    from core_10x.traitable import VaultUser

    try:
        os_login = VaultUser.myname()
    except Exception as exc:
        _fail(f'Failed to determine the OS login: {exc}', 'the process UID has no /etc/passwd entry — see docker/entrypoint.sh for the container pattern')
    else:
        _ok(f'OS login = {os_login!r}')
        print('      Use this exact string for the vault-DB login (--worker).')
        print('      Send it to your DBA / vault admin if they do not already know it')

    # ------------------------------------------------------------------
    # 1. Vault URI configured
    # ------------------------------------------------------------------
    print('\n[1] Vault URI')
    from core_10x.sec_keys import SecKeys

    rc, vault_uri = SecKeys.check_vault_uri(main=True)
    if not rc:
        _fail('XX_MAIN_VAULT_URI is not set', 'set the environment variable: export XX_MAIN_VAULT_URI=mongodb://<host>:<port>/<db>')
        return 1  # nothing else makes sense without this
    _ok(vault_uri)

    keyring_hint = _keyring_setup_hint(vault_uri)

    # ------------------------------------------------------------------
    # 2. Master password in OS keyring
    # ------------------------------------------------------------------
    print('\n[2] Master password (OS keyring)')
    rc, _ = SecKeys.retrieve_master_password()
    if not rc:
        _fail('not found in OS keyring — this machine is not set up for vault access', keyring_hint)
    else:
        _ok('found in OS keyring')

    # ------------------------------------------------------------------
    # 3. Vault login/password in OS keyring
    # ------------------------------------------------------------------
    print('\n[3] Vault login/password (OS keyring)')
    rc, login, _ = SecKeys.retrieve_vault_login_password(vault_uri)
    if not rc:
        _fail('not found in OS keyring — this machine is not set up for vault access', keyring_hint)
    else:
        _ok(f'login = {login!r}')

    if not ok:
        return 1

    # ------------------------------------------------------------------
    # 4. Connect to the vault and check the VaultUser row
    # ------------------------------------------------------------------
    print('\n[4] Vault connection and user record')
    try:
        from core_10x.traitable import Traitable, VaultResourceAccessor, VaultUser

        vault = Traitable.vault_store()
    except Exception as exc:
        _fail(f'Cannot connect to vault ({vault_uri}): {exc}', 'check that the vault server is reachable and that the stored credentials are correct')
        return 1

    with vault:
        me = VaultUser.existing_instance(_throw=False)
        if not me:
            _fail(
                f'No user record found for {VaultUser.myname()!r} in the vault',
                f'XX_MAIN_VAULT_URI may be pointing to the wrong vault (currently: {vault_uri})',
            )
            return 1
        _ok(f'user_id = {me.user_id!r}')

        # ------------------------------------------------------------------
        # 5. List resource accessors and test-connect through each
        # ------------------------------------------------------------------
        print('\n[5] Resource accessors')
        from core_10x.trait_filter import f

        ras = VaultResourceAccessor.load_many(f(username=me.user_id))

        if not ras:
            print('      (none registered — run xx-user-save-credentials, or ask an admin to run xx-admin-save-user-credentials)')
        else:
            for ra in ras:
                label = f'{ra.resource_dt.name}  {ra.resource_uri}  (login: {ra.login})'
                try:
                    ra.resource  # noqa: B018 useless-expression
                    _ok(label)
                except Exception as exc:
                    _fail(
                        label,
                        f'connection failed: {exc} — check that the server is reachable and ask an admin to verify or refresh the stored credentials',
                    )

    print()
    if ok:
        print('All checks passed.')
    else:
        print('One or more checks failed — see FAIL lines above.')

    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
