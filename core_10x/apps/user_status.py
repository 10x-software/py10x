"""User-facing status check for vault and resource-accessor setup.

Installed by ``py10x-core`` as the ``xx-user-status`` console script (see
``pyproject.toml``); also runnable directly as
``python -m core_10x.apps.user_status``.

Exit codes:
  0 — all checks passed
  1 — one or more checks failed
"""

from __future__ import annotations


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
    # 1. Vault URI configured
    # ------------------------------------------------------------------
    print('\n[1] Vault URI')
    from core_10x.sec_keys import SecKeys
    rc, vault_uri = SecKeys.check_vault_uri(main=True)
    if not rc:
        _fail('XX_MAIN_VAULT_URI is not set',
              'set the environment variable: export XX_MAIN_VAULT_URI=mongodb://<host>:<port>/<db>')
        return 1        # nothing else makes sense without this
    _ok(vault_uri)

    # ------------------------------------------------------------------
    # 2. Master password in OS keyring
    # ------------------------------------------------------------------
    print('\n[2] Master password (OS keyring)')
    rc, _ = SecKeys.retrieve_master_password()
    if not rc:
        _fail('not found in OS keyring — self-registration has not been completed on this machine',
              'run: xx-user-init')
    else:
        _ok('found in OS keyring')

    # ------------------------------------------------------------------
    # 3. Vault login/password in OS keyring
    # ------------------------------------------------------------------
    print('\n[3] Vault login/password (OS keyring)')
    rc, login, _ = SecKeys.retrieve_vault_login_password(vault_uri)
    if not rc:
        _fail('not found in OS keyring — self-registration has not been completed on this machine',
              'run: xx-user-init')
    else:
        _ok(f'login = {login!r}')

    if not ok:
        return 1

    # ------------------------------------------------------------------
    # 4. Connect to the vault and check the VaultUser row
    # ------------------------------------------------------------------
    print('\n[4] Vault connection and user record')
    try:
        from core_10x.traitable import Traitable, VaultUser, VaultResourceAccessor
        vault = Traitable.vault_store()
    except Exception as exc:
        _fail(f'Cannot connect to vault ({vault_uri}): {exc}',
              'check that the vault server is reachable and that the stored credentials are correct')
        return 1

    with vault:
        me = VaultUser.existing_instance(_throw=False)
        if not me:
            _fail(f'No user record found for {VaultUser.myname()!r} in the vault',
                  f'XX_MAIN_VAULT_URI may be pointing to the wrong vault '
                  f'(currently: {vault_uri})')
            return 1
        _ok(f'user_id = {me.user_id!r}')

        # ------------------------------------------------------------------
        # 5. List resource accessors and test-connect through each
        # ------------------------------------------------------------------
        print('\n[5] Resource accessors')
        from core_10x.trait_filter import f
        ras = VaultResourceAccessor.load_many(f(username=me.user_id))

        if not ras:
            print('      (none registered — ask an admin to run'
                  ' xx-admin-save-user-credentials for any additional resources)')
        else:
            for ra in ras:
                label = f'{ra.resource_dt.name}  {ra.resource_uri}  (login: {ra.login})'
                try:
                    ra.resource.__class__   # force evaluation — ra.resource is a lazy RT trait
                    _ok(label)
                except Exception as exc:
                    _fail(label,
                          f'connection failed: {exc} — check that the server is reachable '
                          f'and ask an admin to verify or refresh the stored credentials')

    print()
    if ok:
        print('All checks passed.')
    else:
        print('One or more checks failed — see FAIL lines above.')

    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
