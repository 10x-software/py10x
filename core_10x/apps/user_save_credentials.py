"""Save or rotate a resource password for the calling vault user.

Installed as ``xx-user-save-credentials``. See
``docs/USER_ONBOARDING_AUTH.md`` (Part II step 4).
"""

from __future__ import annotations


def main() -> int:
    from core_10x.vault_utils import VaultUtils

    rc = VaultUtils.user_save_credentials()
    if not rc:
        print(rc.error())
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
