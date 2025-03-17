import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key

from core_10x.global_cache import cache

ROOT                = '.xx'
PUBLIC_EXP          = 65537
KEY_SIZE            = 2048
PRIVATE_KEY_FILE    = 'private.pem'
PUBLIC_KEY_FILE     = 'public.pem'
ENCODING            = 'utf-8'

class SecKeys:
    @classmethod
    @cache
    def home_dir(cls) -> str:
        dir = f"{os.path.expanduser('~')}/{ROOT}"
        if os.path.exists(dir):
            assert os.path.isdir(dir), f"{dir} is not a directory"
        else:
            os.mkdir(dir)

        return dir

    @classmethod
    def generate_keys(cls, pwd = None) -> tuple:
        private_key = rsa.generate_private_key(public_exponent = PUBLIC_EXP, key_size= KEY_SIZE, backend = default_backend())
        public_key = private_key.public_key()

        if pwd:
            format  = serialization.PrivateFormat.PKCS8
            algo    = serialization.BestAvailableEncryption(bytes(pwd, encoding = ENCODING))
        else:
            format  = serialization.PrivateFormat.TraditionalOpenSSL
            algo    = serialization.NoEncryption()

        private_key_pem = private_key.private_bytes(encoding = serialization.Encoding.PEM, format = format, encryption_algorithm = algo)
        public_key_pem  = public_key.public_bytes(encoding = serialization.Encoding.PEM, format = serialization.PublicFormat.SubjectPublicKeyInfo)

        return (private_key_pem, public_key_pem)

    @classmethod
    def create_keys(cls, keys: tuple = None) -> tuple:
        private_key, public_key = keys if keys else cls.generate_keys()
        home_dir = cls.home_dir()
        try:
            with open(f'{home_dir}/{PRIVATE_KEY_FILE}', 'wb') as f:
                f.write(private_key)
                os.chmod(f.name, 0o600)

            with open(f'{home_dir}/{PUBLIC_KEY_FILE}', 'wb') as f:
                f.write(public_key)
                os.chmod(f.name, 0o600)

            cls.keys.clear()    #-- cls.keys() will then read from the files
            return (private_key, public_key)

        except Exception:
            return (None, None)

    @classmethod
    @cache
    def keys(cls) -> tuple:
        home_dir = cls.home_dir()
        file = f'{home_dir}/{PRIVATE_KEY_FILE}'
        if os.path.exists(file):
            try:
                with open(file, 'rb') as f:
                    private_key = f.read()

                with open(f'{home_dir}/{PUBLIC_KEY_FILE}', 'rb') as f:
                    public_key = f.read()

                return (private_key, public_key)

            except Exception:
                pass

        return (None, None)

    @classmethod
    def encrypt(cls, message, public_key: bytes = None) -> bytes:
        if type(message) is str:
            message = bytes(message, encoding = ENCODING)

        if public_key is None:
            _, public_key = cls.keys()
            if public_key is None:
                return None

        public_key = load_pem_public_key(public_key)
        return public_key.encrypt(
            message,
            padding.OAEP(
                mgf         = padding.MGF1(algorithm = hashes.SHA256()),
                algorithm   = hashes.SHA256(),
                label       = None
            )
        )

    @classmethod
    def decrypt(cls, encrypted_message: bytes, to_str = True):
        private_key, _ = cls.keys()
        if private_key is None:
            return None

        private_key = load_pem_private_key(private_key, password = None)
        res = private_key.decrypt(
            encrypted_message,
            padding.OAEP(
                mgf         = padding.MGF1(algorithm = hashes.SHA256()),
                algorithm   = hashes.SHA256(),
                label       = None
            )
        )

        if to_str:
            res = res.decode(encoding = ENCODING)

        return res

    @classmethod
    def encrypt_private_key(cls, password) -> bytes:
        if type(password) is str:
            password = bytes(password, encoding = ENCODING)

        private_key, _ = cls.keys()
        if private_key is None:
            return None

        private_key = load_pem_private_key(private_key, password = None)
        return private_key.private_bytes(
            encoding                = serialization.Encoding.PEM,
            format                  = serialization.PrivateFormat.PKCS8,
            encryption_algorithm    = serialization.BestAvailableEncryption(password)
        )

    @classmethod
    def decrypt_private_key(cls, private_key_with_password, password) -> bytes:
        if type(password) is str:
            password = bytes(password, encoding = ENCODING)

        pk = load_pem_private_key(private_key_with_password, password = password)

        return pk.private_bytes(
            encoding                = serialization.Encoding.PEM,
            format                  = serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm    = serialization.NoEncryption()
        )
