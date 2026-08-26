"""Self-registration / new-machine keyring seeding for vault users.

Installed by ``py10x-core`` as the ``xx-user-init`` console script (see
``pyproject.toml``); also runnable directly as
``python -m core_10x.apps.user_init``.

See ``docs/USER_ONBOARDING_AUTH.md`` for the full procedure, including the
``--functional-account`` mode this module implements.
"""

from __future__ import annotations

import json
import os
import sys

import keyring

from core_10x.environment_variables import EnvVars
from core_10x.functional_account_keyring import FunctionalAccountKeyring
from core_10x.rc import RC, RC_TRUE
from core_10x.sec_keys import SecKeys
from core_10x.trait_definition import RT
from core_10x.traitable import VaultUser
from core_10x.traitable_cli import TraitableCli
from core_10x.vault_utils import VaultUtils


class UserInitCli(TraitableCli):
    """Register a vault user on this machine, or seed the OS keyring for an existing user.

    Usage:
    xx-user-init                 first-time registration (default)
    xx-user-init --new-user      first-time registration: create VaultUser + keys and seed OS keyring
    xx-user-init --new-machine   existing user on a new machine: prove master password and seed local OS keyring
    xx-user-init --functional-account --output-file /path/to/manifest
                                  non-interactive registration inside a functional-account
                                  container; writes the manifest to --output-file (e.g. FIFO)
                                  for a wrapper (e.g. xx-functional-account-init) to provision.
    """

    new_user: bool = RT(False)
    new_machine: bool = RT(False)
    functional_account: bool = RT(False)
    output_file: str = RT('')

    def post_verify(self) -> RC:
        rc = super().post_verify()
        modes_set = sum([self.new_user, self.new_machine, self.functional_account])
        if modes_set > 1:
            return rc + RC(False, 'specify only one of --new-user, --new-machine, or --functional-account')
        if self.output_file and not self.functional_account:
            return rc + RC(False, '--output-file only applies with --functional-account')
        if self.functional_account and not self.output_file:
            return rc + RC(False, '--functional-account requires --output-file (the manifest is never printed)')
        if self.functional_account and not VaultUser.is_functional_account(VaultUser.myname()):
            return rc + RC(
                False,
                f'--functional-account requires the OS account name ({VaultUser.myname()!r}) to start with the '
                f'functional-account prefix ({EnvVars.functional_account_prefix!r}) -- see docker/entrypoint.sh',
            )
        return rc

    def run(self) -> RC:
        if not self.functional_account:
            return VaultUtils.user_init(new_machine=self.new_machine)

        # Forces this backend explicitly rather than trusting ambient auto-discovery: whatever
        # keyring happens to be installed on the machine running this (a real OS keychain isn't
        # unsafe, just unpredictable and not what we want -- this command's job is a portable,
        # readable-back manifest, not writing into one operator's personal keychain). No manifest
        # file exists yet either way -- that's fine, FunctionalAccountKeyring starts empty.
        keyring.set_keyring(FunctionalAccountKeyring())

        # login/password are the vault server's own admin credentials (e.g. a Postgres login),
        # prompted interactively same as the human flow. Identity (VaultUser.myname()) comes from
        # the real OS account -- docker/entrypoint.sh has already renamed it to
        # FUNCTIONAL_ACCOUNT_ID by the time this runs.
        rc = VaultUtils.user_init(master_password=SecKeys.generate_password())
        if not rc:
            return rc

        user_id = VaultUser.myname()
        vault_uri = EnvVars.main_vault_uri
        manifest = [
            {
                'service': EnvVars.master_password_key,
                'username': user_id,
                'password': keyring.get_password(EnvVars.master_password_key, user_id),
            },
            {
                'service': vault_uri,
                'username': user_id,
                'password': keyring.get_password(vault_uri, user_id),
            },
        ]
        payload = json.dumps(manifest)
        secret_name = FunctionalAccountKeyring.secret_name(user_id)

        try:
            fd = os.open(self.output_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as f:
                f.write(payload)
        except OSError as ex:
            return RC(False, f'--output-file failed: {ex}')
        print(f'wrote manifest for secret {secret_name!r} to {self.output_file!r}', file=sys.stderr)

        return RC_TRUE


if __name__ == '__main__':
    raise SystemExit(UserInitCli.main())
