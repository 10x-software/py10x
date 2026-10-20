from __future__ import annotations

from typing_extensions import Self

from core_10x.global_cache import standard_key as make_standard_key
from core_10x.resource import OIDC, Resource, ResourceSpec


class OidcSecret(Resource, resource_type=OIDC):
    """OIDC client secret addressed by a client URI.

    The vault stores the client id as the accessor login and the client secret
    as the accessor password. The URI is the whole credential key and is stored
    in plaintext, so the secret belongs in the password and not in the URI.
    A secret must fit in one RSA-OAEP-SHA256 ciphertext (190 bytes with the
    vault's RSA-2048 key).
    """

    s_login_label = 'client id'
    s_secret_label = 'client secret'
    s_instance_kwargs_map = Resource.s_instance_kwargs_map | {
        Resource.PROTOCOL_TAG: (Resource.PROTOCOL_TAG, None),
        Resource.QUERY_TAG: (Resource.QUERY_TAG, ''),
        Resource.FRAGMENT_TAG: (Resource.FRAGMENT_TAG, ''),
    }

    def __init__(self, uri: str, client_id: str | None, client_secret: str | None):
        self.uri = uri
        self.client_id = client_id
        self.client_secret = client_secret

    @classmethod
    def uri_no_dbname(cls, uri: str) -> None:
        return None

    @classmethod
    def instance_from_uri(
        cls, uri: str, username: str = None, password: str = None, _cache: bool = True, _create_if_needed: bool = False
    ) -> OidcSecret:
        # Reject here so a bad save probe does not pass through Resource.instance,
        # whose error text includes the kwargs and therefore the secret.
        if password is not None and not password:
            raise ValueError('OIDC client secret is empty')
        if password is not None and not username:
            raise ValueError('OIDC client id is required')
        return super().instance_from_uri(uri, username=username, password=password, _cache=_cache, _create_if_needed=_create_if_needed)

    @classmethod
    def new_instance(cls, **kwargs) -> Self:
        client_id = kwargs.pop(cls.USERNAME_TAG, None)
        client_secret = kwargs.pop(cls.PASSWORD_TAG, None)
        return cls(ResourceSpec(cls, kwargs).uri(), client_id, client_secret)

    @classmethod
    def standard_key(cls, *args, **kwargs) -> tuple:
        # Base key omits password; the secret is the value being cached.
        return make_standard_key(args, kwargs)

    def on_enter(self):
        pass

    def on_exit(self):
        pass
