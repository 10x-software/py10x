"""Self-registration / new-machine keyring seeding for vault users.

Installed by ``py10x-core`` as the ``xx-user-init`` console script (see
``pyproject.toml``); also runnable directly as
``python -m core_10x.apps.user_init``.

See ``docs/USER_ONBOARDING_AUTH.md`` for the full procedure.
"""

from __future__ import annotations

from core_10x.rc import RC
from core_10x.trait_definition import RT
from core_10x.traitable_cli import TraitableCli
from core_10x.vault_utils import VaultUtils


class UserInitCli(TraitableCli):
    """Register a vault user on this machine, or seed the OS keyring for an existing user.

    Usage:
    xx-user-init                 first-time registration (default)
    xx-user-init --new-user      first-time registration: create VaultUser + keys and seed OS keyring
    xx-user-init --new-machine   existing user on a new machine: prove master password and seed local OS keyring
    """

    new_user: bool = RT(False)
    new_machine: bool = RT(False)

    def post_verify(self) -> RC:
        rc = super().post_verify()
        if self.new_user and self.new_machine:
            return rc + RC(False, 'specify only one of --new-user or --new-machine')
        return rc

    def run(self) -> RC:
        return VaultUtils.user_init(new_machine=self.new_machine)


if __name__ == '__main__':
    raise SystemExit(UserInitCli.main())
