"""Admin entry point: save a ``VaultResourceAccessor`` for an existing user.

Installed by ``py10x-core`` as the ``xx-admin-save-user-credentials`` console
script (see ``pyproject.toml``); also runnable directly as
``python -m core_10x.apps.admin_save_user_credentials``.

See ``docs/USER_ONBOARDING_AUTH.md`` (step 3) for the full procedure.
"""

from __future__ import annotations


def main() -> int:
    from core_10x.vault_utils import VaultUtils

    rc = VaultUtils.admin_save_user_credentials()
    if not rc:
        print(rc.error())
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
