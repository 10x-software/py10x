"""Tests for `SecKeys._verify_keyring_backend` (docs/VAULT_SECURITY_DESIGN.md §3.2) --
`change_master_password`/`change_vault_login_password` refuse to write through any keyring
backend not on the allowlist, so a silently-selected plaintext fallback (e.g. `keyrings.alt`)
can't receive a secret in the first place.
"""

import keyring
import keyring.backend
import pytest
from core_10x.functional_account_keyring import FunctionalAccountKeyring
from core_10x.sec_keys import SecKeys


class _FakePlaintextBackend(keyring.backend.KeyringBackend):
    """Stands in for an unrecognized third-party backend (e.g. keyrings.alt's PlaintextKeyring)."""

    priority = 1

    def get_password(self, service, username):
        return None

    def set_password(self, service, username, password):
        pass

    def delete_password(self, service, username):
        pass


@pytest.fixture(autouse=True)
def _restore_keyring():
    original = keyring.get_keyring()
    yield
    keyring.set_keyring(original)


def test_functional_account_keyring_is_accepted():
    keyring.set_keyring(FunctionalAccountKeyring())
    SecKeys._verify_keyring_backend()  # -- must not raise


def test_unrecognized_backend_is_rejected():
    keyring.set_keyring(_FakePlaintextBackend())
    with pytest.raises(TypeError, match='not a recognized OS-native keyring backend'):
        SecKeys._verify_keyring_backend()


def test_change_master_password_refuses_unrecognized_backend():
    keyring.set_keyring(_FakePlaintextBackend())
    with pytest.raises(TypeError, match='not a recognized OS-native keyring backend'):
        SecKeys.change_master_password('SomePassword1!', override=True)
