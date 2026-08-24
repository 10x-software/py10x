"""Tests for the scrypt-wrapped master-password KDF (docs/VAULT_SECURITY_DESIGN.md §6.1).

`SecKeys.encrypt_private_key` always derives through scrypt now (no legacy write path) --
`decrypt_private_key`/`SecKeys.__init__` stay dual-format on the read side, for rows written
before `master_password_salt` existed.
"""

from unittest.mock import patch

import pytest
from core_10x.sec_keys import SecKeys
from core_10x.traitable import VaultUser
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from infra_10x.duckdb_store import DuckDbStore

MASTER_PASSWORD = 'MyMasterPassword1!'


def _wrap_legacy(private_key_pem: bytes, password: str) -> bytes:
    """Encrypt the way `encrypt_private_key` did before scrypt existed -- raw password, no salt."""
    key = load_pem_private_key(private_key_pem, password=None)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode()),
    )


# ----------------------------------------------------------------------------
#   SecKeys-level: new scheme, legacy compatibility, wrong password
# ----------------------------------------------------------------------------


def test_new_scheme_round_trips():
    private_pem, _public_pem = SecKeys.generate_keys()
    salt = SecKeys.generate_salt()

    wrapped = SecKeys.encrypt_private_key(private_pem, MASTER_PASSWORD, salt)
    recovered = SecKeys.decrypt_private_key(wrapped, MASTER_PASSWORD, salt)

    assert recovered.startswith(b'-----BEGIN')


def test_new_scheme_rejects_wrong_password():
    private_pem, _public_pem = SecKeys.generate_keys()
    salt = SecKeys.generate_salt()
    wrapped = SecKeys.encrypt_private_key(private_pem, MASTER_PASSWORD, salt)

    with pytest.raises(ValueError):  # -- cryptography's own decrypt-failure exception
        SecKeys.decrypt_private_key(wrapped, 'WrongPassword', salt)


def test_legacy_no_salt_row_still_decrypts():
    private_pem, _public_pem = SecKeys.generate_keys()
    legacy_wrapped = _wrap_legacy(private_pem, MASTER_PASSWORD)

    recovered = SecKeys.decrypt_private_key(legacy_wrapped, MASTER_PASSWORD, b'')

    assert recovered.startswith(b'-----BEGIN')


def test_sec_keys_init_handles_both_schemes():
    private_pem, public_pem = SecKeys.generate_keys()
    salt = SecKeys.generate_salt()
    new_wrapped = SecKeys.encrypt_private_key(private_pem, MASTER_PASSWORD, salt)
    legacy_wrapped = _wrap_legacy(private_pem, MASTER_PASSWORD)

    SecKeys(new_wrapped, public_pem, MASTER_PASSWORD, salt)
    SecKeys(legacy_wrapped, public_pem, MASTER_PASSWORD, b'')


# ----------------------------------------------------------------------------
#   VaultUser-level: post_verify() enforces the salt on every new write
# ----------------------------------------------------------------------------


def test_post_verify_rejects_encrypted_private_key_without_salt():
    with patch.object(VaultUser, 'myname', classmethod(lambda cls: 'kdf-hardening-test-user-1')), DuckDbStore.instance():
        u = VaultUser()
        u.set_values(private_key_encrypted=b'fake-encrypted-blob', public_key=b'fake-pub')
        rc = u.save()

    assert not rc
    assert 'master_password_salt' in rc.error()


def test_post_verify_allows_encrypted_private_key_with_salt():
    with patch.object(VaultUser, 'myname', classmethod(lambda cls: 'kdf-hardening-test-user-2')), DuckDbStore.instance():
        u = VaultUser()
        u.set_values(
            private_key_encrypted=b'fake-encrypted-blob',
            public_key=b'fake-pub',
            master_password_salt=b'some-salt',
        )
        rc = u.save()

    assert rc
