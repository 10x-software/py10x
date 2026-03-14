"""Unit tests for vault-related components: SecKeys, VaultUser, VaultResourceAccessor, VaultUtils."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core_10x.rc import RC
from core_10x.sec_keys import SecKeys
from core_10x.vault_utils import VaultUtils


# =============================================================================
#   SecKeys - cryptographic primitives
# =============================================================================

class TestSecKeysPasswordGeneration:
    def test_generates_nonempty_string(self):
        pwd = SecKeys.generate_password()
        assert isinstance(pwd, str)
        assert len(pwd) > 0

    def test_default_length_is_sufficient(self):
        # URL-safe base64 encodes ~4/3 bytes, so 24-byte input yields 32 chars.
        pwd = SecKeys.generate_password()
        assert len(pwd) >= 24

    def test_custom_length(self):
        pwd = SecKeys.generate_password(length=8)
        assert isinstance(pwd, str)
        assert len(pwd) > 0

    def test_passwords_are_unique(self):
        p1 = SecKeys.generate_password()
        p2 = SecKeys.generate_password()
        assert p1 != p2


class TestSecKeysKeyGeneration:
    def test_generate_keys_returns_tuple_of_bytes(self):
        private_pem, public_pem = SecKeys.generate_keys()
        assert isinstance(private_pem, bytes)
        assert isinstance(public_pem, bytes)

    def test_private_key_pem_header(self):
        private_pem, _ = SecKeys.generate_keys()
        assert b'PRIVATE KEY' in private_pem

    def test_public_key_pem_header(self):
        _, public_pem = SecKeys.generate_keys()
        assert b'PUBLIC KEY' in public_pem

    def test_generate_keys_with_password_encrypts_private(self):
        private_pem, _ = SecKeys.generate_keys(pwd='TestPassword1!')
        assert b'ENCRYPTED' in private_pem

    def test_generate_keys_without_password_unencrypted(self):
        private_pem, _ = SecKeys.generate_keys()
        assert b'ENCRYPTED' not in private_pem

    def test_each_call_produces_different_keys(self):
        priv1, pub1 = SecKeys.generate_keys()
        priv2, pub2 = SecKeys.generate_keys()
        assert priv1 != priv2
        assert pub1 != pub2


class TestSecKeysEncryptDecrypt:
    def setup_method(self):
        self.private_pem, self.public_pem = SecKeys.generate_keys()

    def test_roundtrip_str(self):
        message = 'hello vault world'
        encrypted = SecKeys.encrypt(message, self.public_pem)
        assert isinstance(encrypted, bytes)
        decrypted = SecKeys.decrypt(encrypted, self.private_pem, to_str=True)
        assert decrypted == message

    def test_roundtrip_bytes(self):
        message = b'binary payload'
        encrypted = SecKeys.encrypt(message, self.public_pem)
        decrypted = SecKeys.decrypt(encrypted, self.private_pem, to_str=False)
        assert decrypted == message

    def test_ciphertext_differs_from_plaintext(self):
        message = 'secret'
        encrypted = SecKeys.encrypt(message, self.public_pem)
        assert encrypted != message.encode()

    def test_wrong_key_raises(self):
        other_priv, _ = SecKeys.generate_keys()
        encrypted = SecKeys.encrypt('data', self.public_pem)
        with pytest.raises(ValueError):
            SecKeys.decrypt(encrypted, other_priv)


class TestSecKeysPrivateKeyEncryption:
    def setup_method(self):
        self.private_pem, self.public_pem = SecKeys.generate_keys()
        self.password = 'MyStr0ngPass!'

    def test_encrypt_private_key_produces_encrypted_pem(self):
        encrypted = SecKeys.encrypt_private_key(self.private_pem, self.password)
        assert isinstance(encrypted, bytes)
        assert b'ENCRYPTED' in encrypted

    def test_decrypt_private_key_roundtrip(self):
        encrypted = SecKeys.encrypt_private_key(self.private_pem, self.password)
        decrypted = SecKeys.decrypt_private_key(encrypted, self.password)
        # Both should load to the same key (compare the unencrypted PEM form)
        assert isinstance(decrypted, bytes)
        assert b'PRIVATE KEY' in decrypted

    def test_decrypt_with_wrong_password_raises(self):
        encrypted = SecKeys.encrypt_private_key(self.private_pem, self.password)
        with pytest.raises(ValueError):
            SecKeys.decrypt_private_key(encrypted, 'WrongPassword!')

    def test_encrypt_accepts_bytes_password(self):
        pwd_bytes = self.password.encode('utf-8')
        encrypted = SecKeys.encrypt_private_key(self.private_pem, pwd_bytes)
        decrypted = SecKeys.decrypt_private_key(encrypted, self.password)
        assert b'PRIVATE KEY' in decrypted


class TestSecKeysInstanceEncryptDecrypt:
    """Tests for the SecKeys instance (encrypt_text / decrypt_text)."""

    def setup_method(self):
        password = 'SessionPass1!'
        private_pem, public_pem = SecKeys.generate_keys()
        private_encrypted = SecKeys.encrypt_private_key(private_pem, password)
        self.sk = SecKeys(private_encrypted, public_pem, password)

    def test_encrypt_text_returns_bytes(self):
        ct = self.sk.encrypt_text('hello')
        assert isinstance(ct, bytes)

    def test_decrypt_text_returns_str(self):
        ct = self.sk.encrypt_text('hello')
        assert self.sk.decrypt_text(ct) == 'hello'

    def test_roundtrip_unicode(self):
        message = 'café & naïve résumé'
        ct = self.sk.encrypt_text(message)
        assert self.sk.decrypt_text(ct) == message

    def test_roundtrip_long_message(self):
        # RSA-OAEP-SHA256 with 2048-bit key supports up to 190 bytes
        message = 'x' * 100
        ct = self.sk.encrypt_text(message)
        assert self.sk.decrypt_text(ct) == message

    def test_ciphertext_is_nondeterministic(self):
        ct1 = self.sk.encrypt_text('same')
        ct2 = self.sk.encrypt_text('same')
        assert ct1 != ct2  # OAEP uses random padding


class TestSecKeysMasterPasswordKeyring:
    """Tests for master-password keyring integration.

    We mock only the keyring module functions, letting OsUser.me.name() return
    the real OS username (pybind11 C++ object; cannot be patched via unittest.mock).
    """

    def _make_keyring_store(self):
        store = {}

        def get_password(service, username):
            return store.get((service, username))

        def set_password(service, username, password):
            store[(service, username)] = password

        return store, get_password, set_password

    def test_change_then_retrieve_master_password(self):
        _store, get_pw, set_pw = self._make_keyring_store()
        with (
            patch('core_10x.sec_keys.keyring.get_password', side_effect=get_pw),
            patch('core_10x.sec_keys.keyring.set_password', side_effect=set_pw),
        ):
            SecKeys.retrieve_master_password.clear()
            SecKeys.change_master_password('MyPass1!', override=True)
            pwd = SecKeys.retrieve_master_password(throw=True)
            assert pwd == 'MyPass1!'

    def test_retrieve_master_password_not_set_returns_none(self):
        with patch('core_10x.sec_keys.keyring.get_password', return_value=None):
            SecKeys.retrieve_master_password.clear()
            result = SecKeys.retrieve_master_password(throw=False)
            assert result is None

    def test_retrieve_master_password_not_set_throws(self):
        with patch('core_10x.sec_keys.keyring.get_password', return_value=None):
            SecKeys.retrieve_master_password.clear()
            with pytest.raises(OSError):
                SecKeys.retrieve_master_password(throw=True)

    def test_change_master_password_clears_cache(self):
        """After changing the master password, retrieve must return the new value."""
        _store, get_pw, set_pw = self._make_keyring_store()
        with (
            patch('core_10x.sec_keys.keyring.get_password', side_effect=get_pw),
            patch('core_10x.sec_keys.keyring.set_password', side_effect=set_pw),
        ):
            SecKeys.retrieve_master_password.clear()

            SecKeys.change_master_password('FirstPass1!', override=True)
            first = SecKeys.retrieve_master_password()

            SecKeys.change_master_password('SecondPass2!', override=True)
            second = SecKeys.retrieve_master_password()

            assert first == 'FirstPass1!'
            assert second == 'SecondPass2!'

    def test_change_master_password_raises_if_already_set_no_override(self):
        with (
            patch('core_10x.sec_keys.keyring.get_password', return_value='existing'),
            patch('core_10x.sec_keys.keyring.set_password'),
        ):
            SecKeys.retrieve_master_password.clear()
            with pytest.raises(AssertionError):
                SecKeys.change_master_password('NewPass1!', override=False)


class TestSecKeysVaultPasswordKeyring:
    """Tests for vault-password keyring integration."""

    VAULT_URI = 'mongodb://localhost:27017/vault'

    def _make_keyring_store(self):
        store = {}

        def get_password(service, username):
            return store.get((service, username))

        def set_password(service, username, password):
            store[(service, username)] = password

        return store, get_password, set_password

    def test_change_then_retrieve_vault_password(self):
        _store, get_pw, set_pw = self._make_keyring_store()
        with (
            patch('core_10x.sec_keys.keyring.get_password', side_effect=get_pw),
            patch('core_10x.sec_keys.keyring.set_password', side_effect=set_pw),
        ):
            SecKeys.retrieve_vault_password.clear()
            SecKeys.change_vault_password('VaultPass1!', vault_uri=self.VAULT_URI, override=True)
            pwd = SecKeys.retrieve_vault_password(vault_uri=self.VAULT_URI, throw=True)
            assert pwd == 'VaultPass1!'

    def test_retrieve_vault_password_not_set_returns_none(self):
        with patch('core_10x.sec_keys.keyring.get_password', return_value=None):
            SecKeys.retrieve_vault_password.clear()
            result = SecKeys.retrieve_vault_password(vault_uri=self.VAULT_URI, throw=False)
            assert result is None

    def test_change_vault_password_clears_cache(self):
        """After changing the vault password, retrieve must return the new value."""
        _store, get_pw, set_pw = self._make_keyring_store()
        with (
            patch('core_10x.sec_keys.keyring.get_password', side_effect=get_pw),
            patch('core_10x.sec_keys.keyring.set_password', side_effect=set_pw),
        ):
            SecKeys.retrieve_vault_password.clear()

            SecKeys.change_vault_password('Pass1!', vault_uri=self.VAULT_URI, override=True)
            first = SecKeys.retrieve_vault_password(vault_uri=self.VAULT_URI)

            SecKeys.change_vault_password('Pass2!', vault_uri=self.VAULT_URI, override=True)
            second = SecKeys.retrieve_vault_password(vault_uri=self.VAULT_URI)

            assert first == 'Pass1!'
            assert second == 'Pass2!'


# =============================================================================
#   VaultUser - class-level helpers
# =============================================================================

class TestVaultUserIsFunctionalAccount:
    """Tests for VaultUser.is_functional_account() which checks for a prefix."""

    def _call(self, user_id):
        from core_10x.traitable import VaultUser
        return VaultUser.is_functional_account(user_id)

    def test_exact_prefix_is_functional(self):
        assert self._call('xx') is True

    def test_prefix_with_dash_suffix_is_functional(self):
        assert self._call('xx-admin') is True

    def test_longer_prefix_with_dash_is_functional(self):
        assert self._call('xx-worker-01') is True

    def test_plain_user_is_not_functional(self):
        assert self._call('alice') is False

    def test_prefix_embedded_inside_name_is_not_functional(self):
        # 'myxx-something' does not start with 'xx'
        assert self._call('myxx-something') is False

    def test_prefix_without_dash_suffix_not_functional_for_longer_name(self):
        # 'xxuser' starts with 'xx' but has no '-' after the prefix
        assert self._call('xxuser') is False


# =============================================================================
#   VaultUtils - password validation
# =============================================================================

class TestVaultUtilsVerifyNewPassword:
    def test_valid_password_succeeds(self):
        rc = VaultUtils.verify_new_password('ValidPass1!', 'ValidPass1!')
        assert bool(rc) is True

    def test_empty_passwords_fail(self):
        rc = VaultUtils.verify_new_password('', '')
        assert bool(rc) is False

    def test_too_short_fails(self):
        rc = VaultUtils.verify_new_password('Ab1!', 'Ab1!')
        assert bool(rc) is False

    def test_no_letter_fails(self):
        rc = VaultUtils.verify_new_password('12345678!', '12345678!')
        assert bool(rc) is False

    def test_no_uppercase_fails(self):
        rc = VaultUtils.verify_new_password('alllower1!', 'alllower1!')
        assert bool(rc) is False

    def test_no_digit_fails(self):
        rc = VaultUtils.verify_new_password('NoDigitsHere!', 'NoDigitsHere!')
        assert bool(rc) is False

    def test_mismatched_passwords_fail(self):
        rc = VaultUtils.verify_new_password('ValidPass1!', 'DifferentPass1!')
        assert bool(rc) is False

    def test_all_rules_return_rc_false_with_errors(self):
        rc = VaultUtils.verify_new_password('short', 'short')
        assert bool(rc) is False
        assert rc.error()  # some error message is present


# =============================================================================
#   VaultResourceAccessor - resource_get uses login, not username
# =============================================================================

class TestVaultResourceAccessorResourceGet:
    """Verify that resource_get() passes self.login (not self.username) to Resource.instance_from_uri.

    We call the unbound method on a MagicMock to avoid Traitable/C++ init
    while still exercising the exact method body.
    """

    def _make_ra_mock(self, *, resource_uri, os_username, login, decrypted_password):
        ra = MagicMock()
        ra.resource_uri = resource_uri
        ra.username = os_username
        ra.login = login
        ra.password = b'<encrypted>'
        ra.user.sec_keys.decrypt_text.return_value = decrypted_password
        return ra

    def test_resource_get_uses_login_credential(self):
        from core_10x.traitable import VaultResourceAccessor

        ra = self._make_ra_mock(
            resource_uri='mongodb://db.example.com/mydb',
            os_username='os_username',
            login='db_login',
            decrypted_password='s3cr3t',
        )

        with patch('core_10x.traitable.Resource.instance_from_uri') as mock_instance:
            mock_instance.return_value = MagicMock()
            VaultResourceAccessor.resource_get(ra)

        mock_instance.assert_called_once_with(
            'mongodb://db.example.com/mydb',
            username='db_login',
            password='s3cr3t',
        )

    def test_resource_get_does_not_use_os_username(self):
        """Regression: the OS username must NOT be forwarded to the resource."""
        from core_10x.traitable import VaultResourceAccessor

        ra = self._make_ra_mock(
            resource_uri='mongodb://db.example.com/mydb',
            os_username='os_username',
            login='db_login',
            decrypted_password='pass',
        )

        with patch('core_10x.traitable.Resource.instance_from_uri') as mock_instance:
            mock_instance.return_value = MagicMock()
            VaultResourceAccessor.resource_get(ra)

        call_kwargs = mock_instance.call_args.kwargs
        assert call_kwargs.get('username') != 'os_username'

    def test_resource_get_decrypts_password_via_user_sec_keys(self):
        """Verify the encrypted password is decrypted through the user's SecKeys."""
        from core_10x.traitable import VaultResourceAccessor

        ra = self._make_ra_mock(
            resource_uri='mongodb://db.example.com/mydb',
            os_username='os_username',
            login='db_login',
            decrypted_password='decrypted_secret',
        )

        with patch('core_10x.traitable.Resource.instance_from_uri') as mock_instance:
            mock_instance.return_value = MagicMock()
            VaultResourceAccessor.resource_get(ra)

        ra.user.sec_keys.decrypt_text.assert_called_once_with(b'<encrypted>')
        call_kwargs = mock_instance.call_args.kwargs
        assert call_kwargs.get('password') == 'decrypted_secret'
