import secrets

import keyring
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
from keyring.backends.kwallet import DBusKeyring, DBusKeyringKWallet4
from keyring.backends.libsecret import Keyring as LibSecretKeyring
from keyring.backends.macOS import Keyring as MacOSKeyring
from keyring.backends.SecretService import Keyring as SecretServiceKeyring
from keyring.backends.Windows import WinVaultKeyring
from py10x_kernel import OsUser

from core_10x.environment_variables import EnvVars
from core_10x.functional_account_keyring import FunctionalAccountKeyring
from core_10x.global_cache import cache
from core_10x.rc import RC, RC_TRUE

_ACCEPTABLE_KEYRING_BACKENDS = (
    MacOSKeyring,
    WinVaultKeyring,
    SecretServiceKeyring,
    DBusKeyring,
    DBusKeyringKWallet4,
    LibSecretKeyring,
    FunctionalAccountKeyring,
)

PUBLIC_EXP = 65537
KEY_SIZE = 2048
PASSWORD_SIZE = 24
ENCODING = 'utf-8'
OAEP_HASH = hashes.SHA256  # -- mgf/algorithm hash used by every OAEP call in this module

# -- OWASP-minimum scrypt work factor: the master password is derived through this before ever
# reaching PKCS8's own (fixed at 2048, unraisable) inner PBKDF2, so scrypt's cost -- not PBKDF2's --
# gates offline brute-force economics against an exfiltrated VaultUser row. See
# docs/VAULT_SECURITY_DESIGN.md §6.1.
SCRYPT_N = 2**17
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_SALT_SIZE = 16
SCRYPT_KEY_LENGTH = 32


class SecKeys:
    @staticmethod
    def _oaep_padding() -> padding.AsymmetricPadding:
        return padding.OAEP(mgf = padding.MGF1(algorithm = OAEP_HASH()), algorithm = OAEP_HASH(), label = None)

    @staticmethod
    def _max_oaep_plaintext_len(key_size_bits: int) -> int:
        """Max RSA-OAEP plaintext length in bytes: k - 2*hLen - 2 (RFC 8017 §7.1.1), k = key size
        in bytes, hLen = the OAEP hash's digest size. Beyond this, `cryptography` raises a bare
        `ValueError: Encryption failed` with no indication of *why* -- checked for real: 190 bytes
        succeeds, 191 fails, for a 2048-bit key with SHA-256 OAEP, matching this formula exactly.
        """
        return key_size_bits // 8 - 2 * OAEP_HASH().digest_size - 2

    @classmethod
    def _oaep_encrypt(cls, public_key, message: bytes) -> bytes:
        max_len = cls._max_oaep_plaintext_len(public_key.key_size)
        if len(message) > max_len:
            raise ValueError(
                f'message too long for RSA-OAEP encryption with a {public_key.key_size}-bit key: '
                f'{len(message)} bytes > {max_len} byte max'
            )
        return public_key.encrypt(message, cls._oaep_padding())

    @classmethod
    def generate_password(cls, length = PASSWORD_SIZE) -> str:
        return secrets.token_urlsafe(length)

    @classmethod
    def generate_salt(cls) -> bytes:
        return secrets.token_bytes(SCRYPT_SALT_SIZE)

    @staticmethod
    def _derive_key(password, salt: bytes) -> bytes:
        if type(password) is str:
            password = bytes(password, encoding = ENCODING)
        kdf = Scrypt(salt = salt, length = SCRYPT_KEY_LENGTH, n = SCRYPT_N, r = SCRYPT_R, p = SCRYPT_P)
        return kdf.derive(password)

    @classmethod
    @cache
    def retrieve_master_password(cls) -> tuple[RC, str]:
        username = OsUser.me.name()
        v_mp_key = EnvVars.var.master_password_key
        if not v_mp_key:
            return (RC(False, f'MasterPassword key may not be empty ({EnvVars.var_name(v_mp_key)})'), None)

        pwd = keyring.get_password(v_mp_key.value, username)
        if pwd is None:
            return (RC(False, f'MasterPassword for {username} is not found'), None)

        return (RC_TRUE, pwd)

    @staticmethod
    def _verify_keyring_backend():
        active = keyring.get_keyring()
        if not isinstance(active, _ACCEPTABLE_KEYRING_BACKENDS):
            raise TypeError(
                f'refusing to store a secret via {type(active).__module__}.{type(active).__qualname__} -- '
                'not a recognized OS-native keyring backend (or FunctionalAccountKeyring); this is '
                'most likely keyrings.alt or another plaintext-capable fallback'
            )

    @classmethod
    def change_master_password(cls, password: str, override = False):
        username = OsUser.me.name()
        if not override:
            rc, _pwd = cls.retrieve_master_password()
            if rc:
                raise AssertionError(f'MasterPassword for {username} is already set')

        cls._verify_keyring_backend()
        keyring.set_password(EnvVars.master_password_key, username, password)

    @classmethod
    @cache
    def check_vault_uri(cls, main = False) -> tuple[RC, str]:
        v_vault_uri = EnvVars.var.vault_uri if not main else EnvVars.var.main_vault_uri
        if not v_vault_uri:
            return (RC(False, f"'{EnvVars.var_name(v_vault_uri)}' is not defined"), None)

        return (RC_TRUE, v_vault_uri.value)

    s_user_pwd_delim = '\x1f'
    @classmethod
    @cache
    def retrieve_vault_login_password(cls, vault_uri: str) -> tuple[RC, str, str]:
        username = OsUser.me.name()
        if vault_uri is None:
            rc, vault_uri = cls.check_vault_uri()
            if not rc:
                return (rc, None, None)

        login_pwd = keyring.get_password(vault_uri, username)
        if login_pwd is None:
            return (RC(False, f'Vault password for {username} @ {vault_uri} is not found'), None, None)

        try:
            login, pwd = login_pwd.split(cls.s_user_pwd_delim)
        except Exception:
            return (RC(False, f'Vault password for {username} @ {vault_uri} is corrupted'), None, None)

        return (RC_TRUE, login, pwd)

    @classmethod
    def change_vault_login_password(cls, login: str, password: str, vault_uri: str = None, override = False):
        username = OsUser.me.name()
        if vault_uri is None:
            rc, vault_uri = cls.check_vault_uri()
            rc.throw()

        if not override:
            rc, name, pwd = cls.retrieve_vault_login_password(vault_uri)
            if name or pwd:
                raise AssertionError(f'Password for {username} @ {vault_uri} is already set')

        cls._verify_keyring_backend()
        keyring.set_password(vault_uri, username, f'{login}{cls.s_user_pwd_delim}{password}')

    @classmethod
    def generate_keys(cls, pwd = None) -> tuple:
        private_key = rsa.generate_private_key(public_exponent = PUBLIC_EXP, key_size = KEY_SIZE, backend = default_backend())
        public_key = private_key.public_key()

        if pwd:
            format = serialization.PrivateFormat.PKCS8
            algo = serialization.BestAvailableEncryption(bytes(pwd, encoding = ENCODING))
        else:
            format = serialization.PrivateFormat.TraditionalOpenSSL
            algo = serialization.NoEncryption()

        private_key_pem = private_key.private_bytes(encoding = serialization.Encoding.PEM, format = format,
                                                    encryption_algorithm = algo)
        public_key_pem = public_key.public_bytes(encoding = serialization.Encoding.PEM,
                                                 format = serialization.PublicFormat.SubjectPublicKeyInfo)

        return (private_key_pem, public_key_pem)

    @classmethod
    def encrypt(cls, message, public_key_pem: bytes) -> bytes:
        if type(message) is str:
            message = bytes(message, encoding = ENCODING)

        public_key = load_pem_public_key(public_key_pem)
        return cls._oaep_encrypt(public_key, message)

    @classmethod
    def decrypt(cls, encrypted_message: bytes, private_key_pem: bytes, to_str = True):
        private_key = load_pem_private_key(private_key_pem, password = None)
        res = private_key.decrypt(encrypted_message, cls._oaep_padding())

        if to_str:
            res = res.decode(encoding = ENCODING)

        return res

    @classmethod
    def encrypt_private_key(cls, private_key_pem: bytes, password, salt: bytes) -> bytes:
        # Every write always derives through scrypt -- no legacy/unsalted branch here, only on the
        # read side (decrypt_private_key/__init__), for rows written before this existed.
        derived = cls._derive_key(password, salt)

        private_key = load_pem_private_key(private_key_pem, password = None)
        return private_key.private_bytes(
            encoding = serialization.Encoding.PEM,
            format = serialization.PrivateFormat.PKCS8,
            encryption_algorithm = serialization.BestAvailableEncryption(derived),
        )

    @classmethod
    def decrypt_private_key(cls, private_key_with_password, password, salt: bytes = b'') -> bytes:
        if salt:
            password = cls._derive_key(password, salt)
        elif type(password) is str:
            password = bytes(password, encoding = ENCODING)

        pk = load_pem_private_key(private_key_with_password, password = password)
        return pk.private_bytes(
            encoding = serialization.Encoding.PEM,
            format = serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm = serialization.NoEncryption(),
        )

    def __init__(self, private_key_with_password: bytes, public_key_pem: bytes, password, salt: bytes = b''):
        if salt:
            password = SecKeys._derive_key(password, salt)
        elif type(password) is str:
            password = bytes(password, encoding = ENCODING)

        self.private_key = load_pem_private_key(private_key_with_password, password = password)
        self.public_key = load_pem_public_key(public_key_pem)

    def encrypt_text(self, text: str) -> bytes:
        return SecKeys._oaep_encrypt(self.public_key, bytes(text, encoding = ENCODING))

    def decrypt_text(self, encrypted_message: bytes) -> str:
        res = self.private_key.decrypt(encrypted_message, SecKeys._oaep_padding())
        return res.decode(encoding = ENCODING)
