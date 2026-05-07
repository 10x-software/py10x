"""Self-registration entry point for a new vault user.

Installed by ``py10x-core`` as the ``xx-user-init`` console script (see
``pyproject.toml``); also runnable directly as
``python -m core_10x.apps.user_init``.

See ``docs/USER_ONBOARDING_AUTH.md`` (step 2) for the full procedure.
"""

from __future__ import annotations


def main() -> int:
    from core_10x.vault_utils import VaultUtils

    rc = VaultUtils.user_init()
    if not rc:
        print(rc.error())
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
