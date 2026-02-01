import secrets

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key

# fmt: off
PUBLIC_EXP  = 65537
KEY_SIZE    = 2048
PWD_SIZE    = 24
ENCODING    = 'utf-8'
# fmt: on

class SecKeys:
    @classmethod
    def generate_password(cls, length = PWD_SIZE) -> str:
        return secrets.token_urlsafe(length)

    @classmethod
    def generate_keys(cls, pwd=None) -> tuple:
        private_key = rsa.generate_private_key(public_exponent=PUBLIC_EXP, key_size=KEY_SIZE, backend=default_backend())
        public_key = private_key.public_key()

        if pwd:
            format = serialization.PrivateFormat.PKCS8
            algo = serialization.BestAvailableEncryption(bytes(pwd, encoding=ENCODING))
        else:
            format = serialization.PrivateFormat.TraditionalOpenSSL
            algo = serialization.NoEncryption()

        private_key_pem = private_key.private_bytes(encoding=serialization.Encoding.PEM, format=format, encryption_algorithm=algo)
        public_key_pem = public_key.public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo)

        return (private_key_pem, public_key_pem)

    @classmethod
    def encrypt(cls, message, public_key_pem: bytes) -> bytes:
        if type(message) is str:
            message = bytes(message, encoding=ENCODING)

        public_key = load_pem_public_key(public_key_pem)
        # fmt: off
        return public_key.encrypt(
            message,
            padding.OAEP(
                mgf         = padding.MGF1(algorithm = hashes.SHA256()),
                algorithm   = hashes.SHA256(),
                label       = None
            )
        )
        # fmt: on

    @classmethod
    def decrypt(cls, encrypted_message: bytes, private_key_pem: bytes, to_str=True):
        private_key = load_pem_private_key(private_key_pem, password=None)
        # fmt: off
        res = private_key.decrypt(
            encrypted_message,
            padding.OAEP(
                mgf         = padding.MGF1(algorithm = hashes.SHA256()),
                algorithm   = hashes.SHA256(),
                label       = None
            )
        )
        # fmt: on

        if to_str:
            res = res.decode(encoding=ENCODING)

        return res

    @classmethod
    def encrypt_private_key(cls, private_key_pem: bytes, password) -> bytes:
        if type(password) is str:
            password = bytes(password, encoding=ENCODING)

        private_key = load_pem_private_key(private_key_pem, password=None)
        # fmt: off
        return private_key.private_bytes(
            encoding                = serialization.Encoding.PEM,
            format                  = serialization.PrivateFormat.PKCS8,
            encryption_algorithm    = serialization.BestAvailableEncryption(password),
        )
        # fmt: on

    @classmethod
    def decrypt_private_key(cls, private_key_with_password, password) -> bytes:
        if type(password) is str:
            password = bytes(password, encoding=ENCODING)

        pk = load_pem_private_key(private_key_with_password, password=password)
        # fmt: off
        return pk.private_bytes(
            encoding                = serialization.Encoding.PEM,
            format                  = serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm    = serialization.NoEncryption(),
        )
        # fmt: on

    def __init__(self, private_key_with_password: bytes, public_key_pem: bytes, password):
        if type(password) is str:
            password = bytes(password, encoding=ENCODING)

        self.private_key    = load_pem_private_key(private_key_with_password, password=password)
        self.public_key     = load_pem_public_key(public_key_pem)

    def encrypt_text(self, text: str) -> bytes:
        message = bytes(text, encoding=ENCODING)
        # fmt: off
        return self.public_key.encrypt(
            message,
            padding.OAEP(
                mgf         = padding.MGF1(algorithm = hashes.SHA256()),
                algorithm   = hashes.SHA256(),
                label       = None
            )
        )

    def decrypt_text(self, encrypted_message: bytes) -> str:
        # fmt: off
        res = self.private_key.decrypt(
            encrypted_message,
            padding.OAEP(
                mgf         = padding.MGF1(algorithm = hashes.SHA256()),
                algorithm   = hashes.SHA256(),
                label       = None
            )
        )
        # fmt: on

        return res.decode(encoding=ENCODING)
