"""OIDC client secrets stored through ``CONCRETE_RESOURCE.OIDC`` / ``NamedOidc``.

The secret is the vault password. The credential key is the exact URI.
Nothing here contacts an identity provider.
"""

from __future__ import annotations

import core_10x.vault_utils as vault_utils_mod
import pytest
from core_10x.concrete_resource import CONCRETE_RESOURCE
from core_10x.exec_control import CACHE_ONLY
from core_10x.oidc_secret import OidcSecret
from core_10x.testlib.vault_env import vault_env
from core_10x.traitable import NamedOidc, NamedResource, Traitable, VaultResourceAccessor
from core_10x.vault_utils import VaultUtils

CLIENT_A = 'https://idp.example/realms/acme/clients/payments-api'
CLIENT_B = 'https://idp.example/realms/acme/clients/billing-api'
CLIENT_A_QUERY = 'https://idp.example/realms/acme/clients/payments-api?audience=api'
CLIENT_ID = 'payments-api'
SECRET = 'oidc-client-secret-1'
SECRET_B = 'oidc-client-secret-2'

ALICE, ALICE_VAULT_PWD, ALICE_MASTER = 'alice_oidc', 'AliceOidc7!', 'AliceMaster9!'


@pytest.fixture(autouse=True)
def _clear_oidc_cache():
    OidcSecret.s_instances.clear()
    yield
    OidcSecret.s_instances.clear()


def test_oidc_is_a_named_resource_member():
    assert CONCRETE_RESOURCE.OIDC.value is OidcSecret
    assert NamedOidc.s_resource_dt is CONCRETE_RESOURCE.OIDC
    assert NamedOidc.s_bundle_base is NamedResource
    assert OidcSecret.uri_no_dbname(CLIENT_A) is None


def test_instance_holds_the_secret_outside_the_uri():
    opened = OidcSecret.instance_from_uri(CLIENT_A, username=CLIENT_ID, password=SECRET)
    assert opened.client_id == CLIENT_ID
    assert opened.client_secret == SECRET
    assert opened.uri == CLIENT_A
    assert SECRET not in opened.uri

    queried = OidcSecret.instance_from_uri(CLIENT_A_QUERY, username=CLIENT_ID, password=SECRET, _cache=False)
    assert queried.uri == CLIENT_A_QUERY
    assert SECRET not in queried.uri

    again = OidcSecret.instance_from_uri(CLIENT_A, username=CLIENT_ID, password=SECRET)
    rotated = OidcSecret.instance_from_uri(CLIENT_A, username=CLIENT_ID, password=SECRET_B)
    assert again is opened
    assert rotated is not opened
    assert rotated.client_secret == SECRET_B


def test_instance_without_credentials_has_no_secret():
    opened = OidcSecret.instance_from_uri(CLIENT_A)
    assert opened.client_id is None
    assert opened.client_secret is None
    assert opened.uri == CLIENT_A


def test_empty_secret_is_rejected_without_echoing_it():
    with pytest.raises(ValueError, match='client secret is empty'):
        OidcSecret.instance_from_uri(CLIENT_A, username=CLIENT_ID, password='')
    with pytest.raises(ValueError, match='client id is required'):
        OidcSecret.instance_from_uri(CLIENT_A, username='', password=SECRET)


def test_save_and_named_resource(vault_env, monkeypatch):  # noqa: F811
    env = vault_env
    env.switch_os_user(ALICE)
    env.run_user_init(vault_login=ALICE, vault_pwd=ALICE_VAULT_PWD, master_pwd=ALICE_MASTER)

    prompts = []

    def _read(prompt=''):
        prompts.append(prompt)
        return env.text_q.pop(0)

    def _secret(prompt=''):
        prompts.append(prompt)
        return env.secret_q.pop(0)

    monkeypatch.setattr('builtins.input', _read)
    monkeypatch.setattr('getpass.getpass', _secret)
    monkeypatch.setattr(vault_utils_mod.getpass, 'getpass', _secret)

    oidc_idx = CONCRETE_RESOURCE.all_names().index('OIDC')
    env.text_q.extend([str(oidc_idx), CLIENT_A, CLIENT_ID])
    env.secret_q.append(SECRET)
    VaultUtils.user_save_credentials().throw()

    assert any('client id' in prompt for prompt in prompts)
    assert any('client secret' in prompt for prompt in prompts)

    with Traitable.vault_store():
        ra = VaultResourceAccessor.retrieve_ra(CONCRETE_RESOURCE.OIDC, CLIENT_A)
        assert ra.resource_uri == CLIENT_A
        assert SECRET not in ra.resource_uri
        assert ra.login == CLIENT_ID
        assert ra.user.sec_keys.decrypt_text(ra.password) == SECRET

        with pytest.raises(ValueError, match=r'OIDC\(https://idp.example/realms/acme/clients/billing-api\)'):
            VaultResourceAccessor.retrieve_ra(CONCRETE_RESOURCE.OIDC, CLIENT_B)

    with CACHE_ONLY():
        named = NamedOidc(logical_name='payments-api')
        named.uri = CLIENT_A
    opened = named.resource_instance()
    assert opened.client_id == CLIENT_ID
    assert opened.client_secret == SECRET
    assert SECRET not in opened.uri
