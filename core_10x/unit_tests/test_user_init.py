"""CLI routing for ``xx-user-init`` (``UserInitCli``). Vault I/O is mocked."""

from __future__ import annotations

import json
import sys

import keyring
import pytest
from core_10x.apps.user_init import UserInitCli
from core_10x.environment_variables import EnvVars
from core_10x.rc import RC, RC_TRUE
from core_10x.sec_keys import SecKeys
from core_10x.traitable import VaultUser
from core_10x.vault_utils import VaultUtils


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


def _forbid_real_keyring(monkeypatch):
    def _banned(*_args, **_kwargs):
        raise AssertionError('test must not touch the real keyring')

    monkeypatch.setattr(keyring, 'get_password', _banned)
    monkeypatch.setattr(keyring, 'set_password', _banned)
    monkeypatch.setattr(keyring, 'delete_password', _banned)


class _Vault:
    """Stand-in for the vault store context. No connection."""

    def __init__(self, user):
        self.user = user

    def auth_user(self):
        return self.user

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def test_functional_account_does_not_store_token_without_a_digit(monkeypatch, tmp_path):
    """A token_urlsafe draw with no digit fails verify_new_password. user_init must not store it."""
    bad = 'AbCdEfGhIjKlMnOpQrStUvWx'  # urlsafe alphabet, no digit
    good = 'AbCdEfGhIjKlMnOpQrStUvW1'
    assert not VaultUtils.verify_new_password(bad, bad)
    assert 'digit' in VaultUtils.verify_new_password(bad, bad).error().lower()
    assert VaultUtils.verify_new_password(good, good)

    generated = []

    def generate_password(cls, length=24):
        value = bad if not generated else good
        generated.append(value)
        return value

    vault_uri = 'postgresql://vault-host:5432/vaultdb'
    monkeypatch.setattr(EnvVars, 'main_vault_uri', vault_uri)
    monkeypatch.setattr(VaultUser, 'myname', classmethod(lambda cls: 'xx-myservice'))
    monkeypatch.setattr(SecKeys, 'generate_password', classmethod(generate_password))
    _forbid_real_keyring(monkeypatch)
    # Argument evaluation constructs the backend before set_keyring; do not install it.
    monkeypatch.setattr(keyring, 'set_keyring', lambda *_args, **_kwargs: None)

    store = {}
    seen = {}

    def user_init(*, master_password, **kwargs):
        seen['master_password'] = master_password
        seen['kwargs'] = kwargs
        user_id = VaultUser.myname()
        store[(EnvVars.master_password_key, user_id)] = master_password
        store[(vault_uri, user_id)] = 'pg_admin\x1ffake-pg-password'
        return RC_TRUE

    monkeypatch.setattr(keyring, 'get_password', lambda service, username: store.get((service, username)))

    out_file = tmp_path / 'manifest.json'
    assert _run(monkeypatch, ['xx-user-init', '--functional-account', '--output-file', str(out_file)], user_init) == 0
    assert generated[0] == bad
    assert len(generated) >= 2
    assert seen['kwargs'] == {}
    assert seen['master_password'] == good
    assert seen['master_password'] != bad

    manifest = json.loads(out_file.read_text())
    assert manifest[0]['password'] == good
    assert VaultUtils.verify_new_password(manifest[0]['password'], manifest[0]['password'])


def test_user_init_new_user_returns_rc_when_create_master_password_fails(monkeypatch):
    """A policy failure from create_master_password is the returned RC, not OSError."""
    bad = 'NoDigitTokenAbcdef'
    assert not VaultUtils.verify_new_password(bad, bad)
    _forbid_real_keyring(monkeypatch)
    monkeypatch.setattr(VaultUser, 'myname', classmethod(lambda cls: 'alice'))
    monkeypatch.setattr(VaultUser, 'existing_instance', lambda *_args, **_kwargs: None)

    def creds(cls, vault_uri, login=None, password=None):
        return RC_TRUE, _Vault('alice'), login, password

    monkeypatch.setattr(VaultUtils, '_get_and_check_vault_credentials', classmethod(creds))

    rc = VaultUtils._user_init_new_user(
        'postgresql://vault-host:5432/vaultdb',
        login='alice',
        password='vault-secret',
        master_password=bad,
    )
    assert not rc
    assert 'digit' in rc.error().lower()


def test_new_user_with_only_vault_login_points_at_new_machine(monkeypatch):
    vault_uri = 'postgresql://vault-host:5432/vaultdb'
    _forbid_real_keyring(monkeypatch)
    monkeypatch.setattr(SecKeys, 'check_vault_uri', classmethod(lambda cls, main=False: (RC_TRUE, vault_uri)))
    monkeypatch.setattr(
        SecKeys,
        'retrieve_master_password',
        classmethod(lambda cls: (RC(False, 'MasterPassword for alice is not found'), None)),
    )
    monkeypatch.setattr(
        SecKeys,
        'retrieve_vault_login_password',
        classmethod(lambda cls, uri: (RC_TRUE, 'alice', 'vault-secret')),
    )

    def new_user(cls, *_args, **_kwargs):
        raise AssertionError('a vault login without a master password must not start registration')

    monkeypatch.setattr(VaultUtils, '_user_init_new_user', classmethod(new_user))

    rc = VaultUtils.user_init(new_machine=False)
    assert not rc
    assert 'xx-user-init --new-machine' in rc.error()
