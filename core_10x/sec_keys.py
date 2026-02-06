import secrets
import keyring

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key

from py10x_core import OsUser
from core_10x.global_cache import cache
from core_10x.environment_variables import EnvVars

PUBLIC_EXP = 65537
KEY_SIZE = 2048
PASSWORD_SIZE = 24
ENCODING = 'utf-8'


class SecKeys:
    @classmethod
    def generate_password(cls, length = PASSWORD_SIZE) -> str:
        return secrets.token_urlsafe(length)

    @classmethod
    @cache
    def retrieve_master_password(cls, throw = True) -> str:
        username = OsUser.me.name()
        v_mp_key = EnvVars.var.master_password_key
        if not v_mp_key:
            raise AssertionError(f'MasterPassword key may not be empty ({EnvVars.var_name(v_mp_key)})')

        pwd = keyring.get_password(v_mp_key.value, username)
        if pwd is None and throw:
            raise OSError(f'MasterPassword for {username} is not found')

        return pwd

    @classmethod
    def change_master_password(cls, password: str, override = False):
        username = OsUser.me.name()
        if not override and cls.retrieve_master_password(throw = False):
            raise AssertionError(f'MasterPassword for {username} is already set')

        keyring.set_password(EnvVars.master_password_key, username, password)

    @classmethod
    @cache
    def check_vault_uri(cls) -> str:
        v_vault_uri = EnvVars.var.vault_ts_store_uri
        if not v_vault_uri:
            raise OSError(f'Vault URI is not specified ({EnvVars.var_name(v_vault_uri)})')

        return v_vault_uri.value

    @classmethod
    @cache
    def retrieve_vault_password(cls, vault_uri: str = None, throw = True) -> str:
        username = OsUser.me.name()
        if vault_uri is None:
            vault_uri = cls.check_vault_uri()

        pwd = keyring.get_password(vault_uri, username)
        if pwd is None and throw:
            raise OSError(f'Password for {username} @ {vault_uri} is not found')

        return pwd

    @classmethod
    def change_vault_password(cls, password: str, vault_uri: str = None, override = False):
        username = OsUser.me.name()
        if vault_uri is None:
            vault_uri = cls.check_vault_uri()

        if not override and cls.retrieve_vault_password(throw = False):
            raise AssertionError(f'Password for {username} @ {vault_uri} is already set')

        keyring.set_password(vault_uri, username, password)

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
        return public_key.encrypt(
            message,
            padding.OAEP(
                mgf = padding.MGF1(algorithm = hashes.SHA256()),
                algorithm = hashes.SHA256(),
                label = None
            )
        )

    @classmethod
    def decrypt(cls, encrypted_message: bytes, private_key_pem: bytes, to_str = True):
        private_key = load_pem_private_key(private_key_pem, password = None)
        res = private_key.decrypt(
            encrypted_message,
            padding.OAEP(
                mgf = padding.MGF1(algorithm = hashes.SHA256()),
                algorithm = hashes.SHA256(),
                label = None
            )
        )

        if to_str:
            res = res.decode(encoding = ENCODING)

        return res

    @classmethod
    def encrypt_private_key(cls, private_key_pem: bytes, password) -> bytes:
        if type(password) is str:
            password = bytes(password, encoding = ENCODING)

        private_key = load_pem_private_key(private_key_pem, password = None)
        return private_key.private_bytes(
            encoding = serialization.Encoding.PEM,
            format = serialization.PrivateFormat.PKCS8,
            encryption_algorithm = serialization.BestAvailableEncryption(password),
        )

    @classmethod
    def decrypt_private_key(cls, private_key_with_password, password) -> bytes:
        if type(password) is str:
            password = bytes(password, encoding = ENCODING)

        pk = load_pem_private_key(private_key_with_password, password = password)
        return pk.private_bytes(
            encoding = serialization.Encoding.PEM,
            format = serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm = serialization.NoEncryption(),
        )

    def __init__(self, private_key_with_password: bytes, public_key_pem: bytes, password):
        if type(password) is str:
            password = bytes(password, encoding = ENCODING)

        self.private_key = load_pem_private_key(private_key_with_password, password = password)
        self.public_key = load_pem_public_key(public_key_pem)

    def encrypt_text(self, text: str) -> bytes:
        message = bytes(text, encoding = ENCODING)
        return self.public_key.encrypt(
            message,
            padding.OAEP(
                mgf = padding.MGF1(algorithm = hashes.SHA256()),
                algorithm = hashes.SHA256(),
                label = None
            )
        )

    def decrypt_text(self, encrypted_message: bytes) -> str:
        res = self.private_key.decrypt(
            encrypted_message,
            padding.OAEP(
                mgf = padding.MGF1(algorithm = hashes.SHA256()),
                algorithm = hashes.SHA256(),
                label = None
            )
        )
        return res.decode(encoding = ENCODING)
