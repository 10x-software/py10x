"""End-to-end test for **functional-account** (unattended service account) vault onboarding.

Complements ``test_user_onboarding.py``: that test exercises the real vault/crypto code paths
for a *human*, but mocks the OS keyring with a plain in-process dict and never touches a real
database — so it can't catch problems specific to (a) a real ``keyring`` backend object, or
(b) a real authenticated resource behind the vault. This test closes both gaps for the
functional-account path:

- the keyring backend is :class:`core_10x.functional_account_keyring.FunctionalAccountKeyring`,
  installed via the real ``keyring.set_keyring(...)`` (not a monkeypatched dict), loaded from an
  on-disk JSON manifest the way a container's mounted Kubernetes Secret would be;
- the vault itself is a real, running, *authenticated* PostgreSQL instance (the ``xx-test-postgres-auth``
  / CI ``setup-postgres`` password-auth instance on port 5433), so ``VaultUtils.user_init``'s
  non-interactive path (``login=``/``password=``/``master_password=``, added for exactly this
  use case) and the resulting ``VaultResourceAccessor`` round-trip run against a real server.

OS identity is faked (``OsUser``/``VaultUser.myname`` monkeypatched) the same way ``vault_env``
does it when this runs as a plain pytest test -- ``OsUser.me`` is a C++ singleton no test can
rename in-process. But when ``FUNCTIONAL_ACCOUNT_ID`` is set in the environment, this test
assumes it's running for real inside the ``docker/`` container: ``docker/entrypoint.sh`` has
already renamed the OS account and set ``PYTHON_KEYRING_BACKEND`` /
``XX_FUNCTIONAL_ACCOUNT_SECRETS_FILE`` so ``keyring`` lazily picks up the real
``FunctionalAccountKeyring`` (reading the mounted secrets file) the first time this test touches
it -- so there's nothing left to fake -- this closes the one remaining boundary Tier 1 can't
reach.
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

import core_10x.sec_keys as sec_keys_mod
import core_10x.traitable as traitable_mod
import keyring
import pytest
from core_10x.concrete_resource import CONCRETE_RESOURCE
from core_10x.environment_variables import EnvVars
from core_10x.functional_account_keyring import FunctionalAccountKeyring
from core_10x.global_cache import _clear_all_caches
from core_10x.resource import Resource
from core_10x.testlib.strict import need
from core_10x.testlib.test_databases import SESSION_DB, SESSION_DB_IS_PINNED
from core_10x.traitable import Traitable, VaultResourceAccessor, VaultUser
from core_10x.vault_roles import VaultRoles
from core_10x.vault_utils import VaultUtils
from dev_10x.postgres_local import PASSWORD_AUTH_PASSWORD, PASSWORD_AUTH_PORT, PASSWORD_AUTH_USER
from infra_10x.postgres_store import PostgresStore

VAULT_URI = f'postgresql://localhost:{PASSWORD_AUTH_PORT}/{SESSION_DB}'
FUNCTIONAL_ACCOUNT_USER_ID = 'xx-e2e-test'
MASTER_PASSWORD = 'FnAcctMaster9!'


@pytest.fixture
def functional_account_env(monkeypatch, tmp_path):
    """Real ``keyring`` backend + a functional-account identity -- real if containerized, faked otherwise."""
    need(
        PostgresStore.is_running_with_auth('localhost', PASSWORD_AUTH_PORT)[0],
        f'password-auth Postgres not running on localhost:{PASSWORD_AUTH_PORT}',
    )
    # Fresh per-process database (SESSION_DB). Vault-DB login must equal OS user_id
    # (docs/VAULT_SECURITY_DESIGN.md §3.4), so the fixture creates a matching PG role.
    admin = PostgresStore.instance_from_uri(VAULT_URI, username=PASSWORD_AUTH_USER, password=PASSWORD_AUTH_PASSWORD, _cache=False, _create_if_needed=True)

    def _ensure_login_role(user_id: str) -> None:
        VaultRoles.setup(admin, worker=user_id, worker_password=PASSWORD_AUTH_PASSWORD).throw()

    container_account_id = os.environ.get('FUNCTIONAL_ACCOUNT_ID')
    if container_account_id:
        # -- Tier 2: inside docker/entrypoint.sh's container. Identity and the keyring backend
        #    are already real; nothing here to fake.
        assert VaultUser.myname() == container_account_id, (
            'entrypoint.sh should have renamed the OS account to FUNCTIONAL_ACCOUNT_ID before this test ran'
        )
        _ensure_login_role(container_account_id)
        monkeypatch.setattr(EnvVars, 'main_vault_uri', VAULT_URI)
        _clear_all_caches()
        yield SimpleNamespace(user_id=container_account_id, vault_login=container_account_id, vault_password=PASSWORD_AUTH_PASSWORD)
        _clear_all_caches()
        _drop_session_db()
        return

    # -- Tier 1: plain pytest run (dev machine / normal CI matrix).
    user_id = FUNCTIONAL_ACCOUNT_USER_ID

    secrets_file = tmp_path / 'keyring.json'
    secrets_file.write_text(json.dumps([]))  # starts empty; user_init populates it via real keyring.set_password

    original_backend = keyring.get_keyring()
    keyring.set_keyring(FunctionalAccountKeyring.from_secrets_file(secrets_file))

    fake_os = SimpleNamespace(me=SimpleNamespace(name=lambda: user_id))
    monkeypatch.setattr(sec_keys_mod, 'OsUser', fake_os)
    monkeypatch.setattr(traitable_mod, 'OsUser', fake_os)
    monkeypatch.setattr(VaultUser, 'myname', classmethod(lambda cls: user_id))
    monkeypatch.setattr(EnvVars, 'main_vault_uri', VAULT_URI)
    _ensure_login_role(user_id)

    _clear_all_caches()
    yield SimpleNamespace(user_id=user_id, vault_login=user_id, vault_password=PASSWORD_AUTH_PASSWORD)

    keyring.set_keyring(original_backend)
    _clear_all_caches()
    _drop_session_db()


def _drop_session_db() -> None:
    if SESSION_DB_IS_PINNED:
        return
    PostgresStore.instance_from_uri(
        Resource.uri_no_dbname(VAULT_URI), username=PASSWORD_AUTH_USER, password=PASSWORD_AUTH_PASSWORD, _cache=False
    ).delete_database(SESSION_DB)


def test_functional_account_self_registers_against_real_vault(functional_account_env):
    user_id = functional_account_env.user_id
    assert VaultUser.is_functional_account(user_id), 'test user_id must look like a functional account (xx- prefix)'
    assert not VaultUser.is_functional_account('alice')

    # -- Self-registration: what a container's entrypoint runs, as the (really) renamed OS
    #    account, right after materializing its secrets file. No getpass/input prompts.
    VaultUtils.user_init(
        login=functional_account_env.vault_login,
        password=functional_account_env.vault_password,
        master_password=MASTER_PASSWORD,
    ).throw()
    # SecKeys.retrieve_* are @cache'd process-globally (keyed without the username, since it
    # reads OsUser.me.name() internally); user_init's own early not-found probe cached a stale
    # negative result before registration wrote the real value. Invalidate it, same as vault_env.
    _clear_all_caches()

    # -- Prove the *real* keyring backend (not a dict monkeypatch) actually received the
    #    secrets that SecKeys.change_master_password / change_vault_login_password wrote.
    assert keyring.get_password(EnvVars.master_password_key, user_id) == MASTER_PASSWORD
    login_pwd = keyring.get_password(VAULT_URI, user_id)
    assert login_pwd == f'{functional_account_env.vault_login}\x1f{functional_account_env.vault_password}'

    with Traitable.vault_store():
        me = VaultUser.existing_instance(user_id=user_id)
        assert me.user_id == user_id
        assert me.public_key and me.private_key_encrypted

        # -- Server-wide RA created during self-registration: resolves against the *real*
        #    authenticated Postgres instance and connects for real.
        ra = VaultResourceAccessor.retrieve_ra(CONCRETE_RESOURCE.TS_STORE, VAULT_URI)
        assert ra.login == functional_account_env.vault_login
        assert me.sec_keys.decrypt_text(ra.password) == functional_account_env.vault_password

        store = ra.resource
        assert store._execute('SELECT 1')[0][0] == 1
