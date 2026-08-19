"""CLI routing for ``xx-user-init`` (``UserInitCli``). Vault I/O is mocked."""

from __future__ import annotations

import json
import sys

import keyring
from core_10x.apps.user_init import UserInitCli
from core_10x.environment_variables import EnvVars
from core_10x.rc import RC_TRUE
from core_10x.traitable import VaultUser


def _run(monkeypatch, argv, user_init):
    monkeypatch.setattr(sys, 'argv', argv)
    monkeypatch.setattr('core_10x.vault_utils.VaultUtils.user_init', user_init)
    return UserInitCli.main()


def test_default_is_new_user(monkeypatch):
    seen = {}

    def user_init(*, new_machine, **_kwargs):
        seen['new_machine'] = new_machine
        return RC_TRUE

    assert _run(monkeypatch, ['xx-user-init'], user_init) == 0
    assert seen['new_machine'] is False


def test_new_user_flag(monkeypatch):
    seen = {}

    def user_init(*, new_machine, **_kwargs):
        seen['new_machine'] = new_machine
        return RC_TRUE

    assert _run(monkeypatch, ['xx-user-init', '--new-user'], user_init) == 0
    assert seen['new_machine'] is False


def test_new_machine_flag(monkeypatch):
    seen = {}

    def user_init(*, new_machine, **_kwargs):
        seen['new_machine'] = new_machine
        return RC_TRUE

    assert _run(monkeypatch, ['xx-user-init', '--new-machine'], user_init) == 0
    assert seen['new_machine'] is True


def test_both_flags_are_rejected(monkeypatch, capsys):
    def user_init(**_kwargs):
        raise AssertionError('VaultUtils.user_init must not run when both flags are set')

    assert _run(monkeypatch, ['xx-user-init', '--new-user', '--new-machine'], user_init) == 1
    assert 'specify only one of --new-user, --new-machine, or --functional-account' in capsys.readouterr().out


def test_functional_account_requires_command(monkeypatch, capsys):
    def user_init(**_kwargs):
        raise AssertionError('VaultUtils.user_init must not run without --command')

    assert _run(monkeypatch, ['xx-user-init', '--functional-account'], user_init) == 1
    assert '--functional-account requires --command' in capsys.readouterr().out


def test_command_requires_functional_account(monkeypatch, capsys):
    def user_init(**_kwargs):
        raise AssertionError('VaultUtils.user_init must not run')

    assert _run(monkeypatch, ['xx-user-init', '--command', 'echo hi'], user_init) == 1
    assert '--command only applies with --functional-account' in capsys.readouterr().out


def test_functional_account_and_new_user_are_mutually_exclusive(monkeypatch, capsys):
    def user_init(**_kwargs):
        raise AssertionError('VaultUtils.user_init must not run')

    argv = ['xx-user-init', '--new-user', '--functional-account', '--command', 'echo hi']
    assert _run(monkeypatch, argv, user_init) == 1
    assert 'specify only one of --new-user, --new-machine, or --functional-account' in capsys.readouterr().out


def test_functional_account_generates_master_password_and_pipes_manifest(monkeypatch, capsys, tmp_path):
    """CLI plumbing only (vault I/O mocked, matching the module docstring): login/password are
    never passed to VaultUtils.user_init (so the real getpass prompts would fire for both), the
    master password is generated rather than supplied, and the resulting manifest is piped --
    never printed -- into --command with {secret_name} substituted. Identity itself
    (VaultUser.myname()) is not this CLI's concern -- it comes from the real OS account, already
    renamed by docker/entrypoint.sh by the time this runs for real."""
    vault_uri = 'postgresql://vault-host:5432/vaultdb'
    monkeypatch.setattr(EnvVars, 'main_vault_uri', vault_uri)
    original_backend = keyring.get_keyring()

    seen = {}

    def user_init(*, master_password, **kwargs):
        seen['master_password'] = master_password
        seen['other_kwargs'] = kwargs
        # Simulate what the real VaultUtils.user_init would have written, into whichever keyring
        # _run_functional_account already installed for this call.
        user_id = VaultUser.myname()
        keyring.set_password(EnvVars.master_password_key, user_id, master_password)
        keyring.set_password(vault_uri, user_id, 'pg_admin\x1ffake-pg-password')
        return RC_TRUE

    out_file = tmp_path / 'captured.json'
    argv = [
        'xx-user-init',
        '--functional-account',
        '--command', f'tee {out_file}',
    ]
    try:
        rc = _run(monkeypatch, argv, user_init)
    finally:
        keyring.set_keyring(original_backend)

    assert rc == 0
    assert seen['other_kwargs'] == {}   # no login/password passed -> both prompted interactively
    assert seen['master_password']   # generated (SecKeys.generate_password()), not supplied
    assert len(seen['master_password']) >= 20   # not a trivially short placeholder

    stdout = capsys.readouterr().out
    assert stdout == ''   # manifest must never be printed

    manifest = json.loads(out_file.read_text())
    user_id = VaultUser.myname()
    assert manifest == [
        {'service': EnvVars.master_password_key, 'username': user_id, 'password': seen['master_password']},
        {'service': vault_uri, 'username': user_id, 'password': 'pg_admin\x1ffake-pg-password'},
    ]
