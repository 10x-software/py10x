"""CLI routing for ``xx-user-init`` (``UserInitCli``). Vault I/O is mocked."""

from __future__ import annotations

import json
import sys

import keyring
import pytest
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


def test_functional_account_requires_output_file(monkeypatch, capsys):
    def user_init(**_kwargs):
        raise AssertionError('VaultUtils.user_init must not run without --output-file')

    assert _run(monkeypatch, ['xx-user-init', '--functional-account'], user_init) == 1
    assert '--functional-account requires --output-file' in capsys.readouterr().out


def test_output_file_requires_functional_account(monkeypatch, capsys, tmp_path):
    def user_init(**_kwargs):
        raise AssertionError('VaultUtils.user_init must not run')

    assert _run(monkeypatch, ['xx-user-init', '--output-file', str(tmp_path / 'm.json')], user_init) == 1
    assert '--output-file only applies with --functional-account' in capsys.readouterr().out


def test_functional_account_and_new_user_are_mutually_exclusive(monkeypatch, capsys, tmp_path):
    def user_init(**_kwargs):
        raise AssertionError('VaultUtils.user_init must not run')

    argv = ['xx-user-init', '--new-user', '--functional-account', '--output-file', str(tmp_path / 'm.json')]
    assert _run(monkeypatch, argv, user_init) == 1
    assert 'specify only one of --new-user, --new-machine, or --functional-account' in capsys.readouterr().out


def test_functional_account_rejects_non_prefixed_os_identity(monkeypatch, capsys, tmp_path):
    """Defense-in-depth, not a fix for a currently-live gap (infra_10x/mongodb_utils.py's
    is_functional_account() consumer has no live callers today -- see docs/VAULT_SECURITY_DESIGN.md
    §3.3): registering a "functional account" whose real OS identity doesn't actually carry the
    "xx-" prefix should still be rejected before VaultUtils.user_init (or anything else) runs, so
    the convention holds before anything else grows to depend on it."""

    def user_init(**_kwargs):
        raise AssertionError('VaultUtils.user_init must not run for a non-prefixed identity')

    monkeypatch.setattr(VaultUser, 'myname', classmethod(lambda cls: 'not-a-functional-account'))
    argv = ['xx-user-init', '--functional-account', '--output-file', str(tmp_path / 'm.json')]
    assert _run(monkeypatch, argv, user_init) == 1
    assert 'to start with the functional-account prefix' in capsys.readouterr().out


@pytest.mark.skipif(
    sys.platform == 'win32',
    reason='--functional-account is a Linux/Docker-container command (docker/entrypoint.sh); --output-file is not exercised on Windows',
)
def test_functional_account_writes_manifest_to_output_file(monkeypatch, capsys, tmp_path):
    """--output-file is the mode an outer wrapper (xx-functional-account-init) uses: the manifest
    is written to a path (a plain file here; a bind-mounted FIFO for the real wrapper -- opened
    the same way either way) instead of piped into a subprocess, and still never printed."""
    vault_uri = 'postgresql://vault-host:5432/vaultdb'
    monkeypatch.setattr(EnvVars, 'main_vault_uri', vault_uri)
    monkeypatch.setattr(VaultUser, 'myname', classmethod(lambda cls: 'xx-myservice'))
    original_backend = keyring.get_keyring()

    seen = {}

    def user_init(*, master_password, **kwargs):
        seen['master_password'] = master_password
        seen['other_kwargs'] = kwargs
        user_id = VaultUser.myname()
        keyring.set_password(EnvVars.master_password_key, user_id, master_password)
        keyring.set_password(vault_uri, user_id, 'pg_admin\x1ffake-pg-password')
        return RC_TRUE

    out_file = tmp_path / 'manifest.json'
    argv = ['xx-user-init', '--functional-account', '--output-file', str(out_file)]
    try:
        rc = _run(monkeypatch, argv, user_init)
    finally:
        keyring.set_keyring(original_backend)

    assert rc == 0
    assert seen['other_kwargs'] == {}
    assert seen['master_password']

    stdout = capsys.readouterr().out
    assert stdout == ''  # manifest must never be printed

    manifest = json.loads(out_file.read_text())
    user_id = VaultUser.myname()
    assert manifest == [
        {'service': EnvVars.master_password_key, 'username': user_id, 'password': seen['master_password']},
        {'service': vault_uri, 'username': user_id, 'password': 'pg_admin\x1ffake-pg-password'},
    ]
