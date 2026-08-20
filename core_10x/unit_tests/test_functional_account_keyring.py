"""Unit tests for `FunctionalAccountKeyring` itself (no real vault/OS keyring involved -- see
`test_functional_account_vault.py` for the end-to-end vault flow)."""

from __future__ import annotations

import json

import keyring.errors
import pytest
from core_10x.functional_account_keyring import SECRETS_FILE_ENV_VAR, FunctionalAccountKeyring


def test_no_env_var_starts_empty_not_raising(monkeypatch):
    monkeypatch.delenv(SECRETS_FILE_ENV_VAR, raising=False)
    fk = FunctionalAccountKeyring()  # must never raise -- keyring's auto-discovery probe depends on this
    assert fk.get_password('svc', 'user') is None


def test_env_var_pointing_at_missing_file_starts_empty_not_raising(monkeypatch, tmp_path):
    missing = tmp_path / 'does-not-exist.json'
    monkeypatch.setenv(SECRETS_FILE_ENV_VAR, str(missing))
    fk = FunctionalAccountKeyring()  # must not raise FileNotFoundError
    assert fk.get_password('svc', 'user') is None


def test_env_var_pointing_at_real_file_loads_entries(monkeypatch, tmp_path):
    manifest = tmp_path / 'keyring.json'
    manifest.write_text(json.dumps([{'service': 'svc', 'username': 'user', 'password': 'pw'}]))
    monkeypatch.setenv(SECRETS_FILE_ENV_VAR, str(manifest))
    fk = FunctionalAccountKeyring()
    assert fk.get_password('svc', 'user') == 'pw'
    assert fk.get_password('svc', 'someone-else') is None


def test_from_secrets_file_missing_path_starts_empty(tmp_path):
    fk = FunctionalAccountKeyring.from_secrets_file(tmp_path / 'nope.json')
    assert fk.get_password('svc', 'user') is None


def test_from_secrets_file_existing_path_loads_entries(tmp_path):
    manifest = tmp_path / 'keyring.json'
    manifest.write_text(json.dumps([{'service': 'svc', 'username': 'user', 'password': 'pw'}]))
    fk = FunctionalAccountKeyring.from_secrets_file(manifest)
    assert fk.get_password('svc', 'user') == 'pw'


def test_set_then_get_round_trips_in_memory():
    fk = FunctionalAccountKeyring()
    fk.set_password('svc', 'user', 'pw')
    assert fk.get_password('svc', 'user') == 'pw'


def test_delete_missing_entry_raises_password_delete_error():
    fk = FunctionalAccountKeyring()
    with pytest.raises(keyring.errors.PasswordDeleteError):
        fk.delete_password('svc', 'user')


def test_delete_existing_entry():
    fk = FunctionalAccountKeyring()
    fk.set_password('svc', 'user', 'pw')
    fk.delete_password('svc', 'user')
    assert fk.get_password('svc', 'user') is None


def test_secret_name_derives_from_user_id():
    assert FunctionalAccountKeyring.secret_name('xx-myservice') == 'xx-myservice-vault-keyring'
