"""End-to-end test for Part II of ``docs/USER_ONBOARDING_AUTH.md``.

Exercises ``user_init``, ``admin_save_user_credentials``, and
``VaultResourceAccessor`` against a shared in-memory DuckDB vault. The
``vault_env`` fixture provides the vault directly (``can_serve_as_vault`` /
``is_vault_admin`` patched on DuckDB) — it does **not** run
``xx-vault-setup-roles``; that is covered by ``test_vault_roles.py`` and by
``test_functional_account_vault`` (real Postgres needs ``VaultRoles.setup``).

Scenario (Part II, after Part I deployment):

1. Vault admin bootstraps with ``user_init`` (fixture stands in for issued
   vault-DB login + ``xx-user-init``).
2. Admin transmits Alice's vault login + password OOB (declared in test).
3. Alice self-registers with ``user_init``.
4. Vault admin runs ``admin_save_user_credentials`` for a relational DB.
5. Alice retrieves and decrypts credentials via ``retrieve_ra``.

Mocked boundaries: in-memory keyring, ``input``/``getpass``, ``OsUser`` /
``VaultUser.myname``, and DuckDB URI/protocol shims.
"""

from __future__ import annotations

import pytest
from core_10x.concrete_resource import CONCRETE_RESOURCE
from core_10x.environment_variables import EnvVars
from core_10x.resource import Resource
from core_10x.sec_keys import SecKeys
from core_10x.testlib.vault_env import VAULT_URI, vault_env
from core_10x.trait_method_error import TraitMethodError
from core_10x.traitable import Traitable, VaultResourceAccessor, VaultUser
from core_10x.vault_utils import VaultUtils
from infra_10x.duckdb_store import DuckDbStore

# -- URIs and credentials specific to the user-onboarding scenario ---------
# (The ``vault_env`` fixture itself lives in ``core_10x.testlib.vault_env``
# and uses its own internal ``VAULT_URI`` matching the host below.)

VAULT_HOST_URI = 'duckdb://vaulthost.example.com'  # no port number - should be added by round trip
MAIN_ON_VAULT = 'duckdb://vaulthost.example.com:27017/main'  # different db, same host
PG_URI = 'postgresql://pghost.example.com:5432/analytics'

ADMIN, ADMIN_VAULT_PWD, ADMIN_MASTER = 'admin', 'AdminVault7!', 'AdminMaster9!'
ALICE, ALICE_VAULT_PWD, ALICE_MASTER = 'alice', 'AliceVault7!', 'AliceMaster9!'
PG_PWD = 'PgWorker3!'


# -- The scenario ---------------------------------------------------------


def test_admin_user_onboarding_information_flow(vault_env):  # noqa: F811  (pytest fixture)
    env = vault_env

    # ----------------------------------------------------------------- 0
    # Sysadmin (out of band) created vault DB accounts for the admin and
    # alice, with vault passwords. We just declare them here; the
    # ``MongodbAdmin.update_user(...)`` call that produces them in
    # production is exercised by infra_10x tests.

    # ----------------------------------------------------------------- 1
    # ADMIN bootstraps themselves.
    env.switch_os_user(ADMIN)
    env.run_user_init(vault_login=ADMIN, vault_pwd=ADMIN_VAULT_PWD, master_pwd=ADMIN_MASTER)

    # ----------------------------------------------------------------- 2
    # Admin transmits (vault_login=ALICE, vault_pwd=ALICE_VAULT_PWD) to
    # alice out of band.

    # ----------------------------------------------------------------- 3
    # ALICE self-registers.
    env.switch_os_user(ALICE)
    env.run_user_init(vault_login=ALICE, vault_pwd=ALICE_VAULT_PWD, master_pwd=ALICE_MASTER)

    # Verify the bookkeeping that admin's step (5) will rely on:
    with Traitable.vault_store():
        me = VaultUser.existing_instance(user_id=ALICE)
        assert me.user_id == ALICE
        assert me.public_key and me.private_key_encrypted

        # Server-wide RA created during self-registration: any other DB on
        # the same vault host is now reachable without a per-DB admin step.
        host_ra = VaultResourceAccessor.retrieve_ra(
            CONCRETE_RESOURCE.TS_STORE,
            VAULT_HOST_URI,
        )
        assert host_ra.login == ALICE
        assert me.sec_keys.decrypt_text(host_ra.password) == ALICE_VAULT_PWD

    # ----------------------------------------------------------------- 4/5
    # ADMIN grants using the vault login issued in step 2 (same as OS user_id).
    env.switch_os_user(ADMIN)
    rel_db_idx = CONCRETE_RESOURCE.all_names().index('REL_DB')
    env.text_q.extend(
        [
            ALICE,  # 'Enter the vault login issued to this user:'
            str(rel_db_idx),  # 'Choose CONCRETE_RESOURCE ...'
            PG_URI,  # 'Enter URI for REL_DB:'
            '',  # 'Enter login name (alice):' -> default
        ]
    )
    env.secret_q.append(PG_PWD)  # 'Enter password for alice:'

    VaultUtils.admin_save_user_credentials().throw()
    assert not env.text_q and not env.secret_q

    # ----------------------------------------------------------------- 6
    # ALICE retrieves credentials and confirms decryption.
    env.switch_os_user(ALICE)
    with Traitable.vault_store():
        # 6a) Different DB on the vault host, resolved via uri_no_dbname
        #     fallback against the registration-time RA.
        ra = VaultResourceAccessor.retrieve_ra(
            CONCRETE_RESOURCE.TS_STORE,
            MAIN_ON_VAULT,
        )
        assert ra.resource_uri == MAIN_ON_VAULT, 'returned RA reports the requested URI, not the registered one'
        assert ra.login == ALICE
        assert ra.user.sec_keys.decrypt_text(ra.password) == ALICE_VAULT_PWD

        # 6b) The relational DB, resolved against the admin-supplied RA.
        ra_pg = VaultResourceAccessor.retrieve_ra(
            CONCRETE_RESOURCE.REL_DB,
            PG_URI,
        )
        assert ra_pg.login == ALICE
        assert ra_pg.user.sec_keys.decrypt_text(ra_pg.password) == PG_PWD


def test_admin_cannot_decrypt_alice_credentials(vault_env):  # noqa: F811  (pytest fixture)
    """Regression guard: even though the admin holds the vault open and can
    save resource passwords for alice (using only her public key), nothing
    in the admin's environment lets them recover plaintext credentials for
    other users."""

    env = vault_env

    # Bootstrap admin and alice as in the main test.
    env.switch_os_user(ADMIN)
    env.run_user_init(vault_login=ADMIN, vault_pwd=ADMIN_VAULT_PWD, master_pwd=ADMIN_MASTER)
    env.switch_os_user(ALICE)
    env.run_user_init(vault_login=ALICE, vault_pwd=ALICE_VAULT_PWD, master_pwd=ALICE_MASTER)

    # Admin saves an RA for alice's REL_DB (using only her public key).
    env.switch_os_user(ADMIN)
    with Traitable.vault_store():
        VaultResourceAccessor.save_ra(
            resource_dt=CONCRETE_RESOURCE.REL_DB,
            resource_uri=PG_URI,
            password=PG_PWD,
            login=ALICE,
            username=ALICE,
        ).throw()

        # Trying to decrypt as the admin must fail — the vault has alice's
        # *encrypted* private key, but only alice's master password (kept
        # in alice's OS keyring) can unlock it.
        ra = VaultResourceAccessor.retrieve_ra(
            CONCRETE_RESOURCE.REL_DB,
            PG_URI,
            username=ALICE,
        )
        with pytest.raises(TraitMethodError):
            ra.user.sec_keys.decrypt_text(ra.password)

    # Alice can decrypt on her own machine.
    env.switch_os_user(ALICE)
    with Traitable.vault_store():
        ra = VaultResourceAccessor.retrieve_ra(
            CONCRETE_RESOURCE.REL_DB,
            PG_URI,
            username=ALICE,
        )
        assert ra.user.sec_keys.decrypt_text(ra.password) == PG_PWD


def test_user_save_credentials_own_and_rotate(vault_env, monkeypatch):  # noqa: F811
    """A user can add and rotate their own resource password without a vault admin."""
    env = vault_env
    env.switch_os_user(ALICE)
    env.run_user_init(vault_login=ALICE, vault_pwd=ALICE_VAULT_PWD, master_pwd=ALICE_MASTER)

    class _Ok:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    monkeypatch.setattr(CONCRETE_RESOURCE.REL_DB.value, 'instance_from_uri', classmethod(lambda cls, *a, **k: _Ok()))
    rel_db_idx = CONCRETE_RESOURCE.all_names().index('REL_DB')
    env.text_q.extend([str(rel_db_idx), PG_URI, ''])
    env.secret_q.append(PG_PWD)
    VaultUtils.user_save_credentials().throw()
    with Traitable.vault_store():
        ra = VaultResourceAccessor.retrieve_ra(CONCRETE_RESOURCE.REL_DB, PG_URI)
        assert ra.user.sec_keys.decrypt_text(ra.password) == PG_PWD

    env.text_q.extend([str(rel_db_idx), PG_URI, ''])
    env.secret_q.append('NewPgPwd9!')
    VaultUtils.user_save_credentials().throw()
    with Traitable.vault_store():
        ra = VaultResourceAccessor.retrieve_ra(CONCRETE_RESOURCE.REL_DB, PG_URI)
        assert ra.user.sec_keys.decrypt_text(ra.password) == 'NewPgPwd9!'


def test_user_init_requires_vault_login_equal_os_user(vault_env, monkeypatch):  # noqa: F811
    """Vault-DB login must equal OS user_id (Mongo connection user == identity)."""
    env = vault_env
    env.switch_os_user(ALICE)
    monkeypatch.setattr(DuckDbStore, 'auth_user', lambda self: 'alice_db')
    rc = VaultUtils.user_init(
        login='alice_db',
        password=ALICE_VAULT_PWD,
        master_password=ALICE_MASTER,
    )
    assert not rc
    assert 'must equal OS user' in rc.error()


def test_suspended_account_cannot_decrypt(vault_env):  # noqa: F811
    """`sec_keys_get()` is the choke point for resource-credential and private-key
    decrypt; suspension is gated there. `RT(T.EVAL_ONCE)`: a process that already
    evaluated `.sec_keys` before suspension keeps the cached value. See
    docs/VAULT_SECURITY_DESIGN.md §3.2.
    """
    env = vault_env
    env.switch_os_user(ALICE)
    env.run_user_init(vault_login=ALICE, vault_pwd=ALICE_VAULT_PWD, master_pwd=ALICE_MASTER)

    env.switch_os_user(ADMIN)
    env.run_user_init(vault_login=ADMIN, vault_pwd=ADMIN_VAULT_PWD, master_pwd=ADMIN_MASTER)
    with Traitable.vault_store():
        me = VaultUser.existing_instance(user_id=ALICE)
        me.set_values(suspended=True).throw()
        me.save().throw()

    env.switch_os_user(ALICE)
    with Traitable.vault_store():
        me = VaultUser.existing_instance(user_id=ALICE)
        # -- property-getter exceptions get wrapped by the framework -- TraitMethodError, same as
        # test_admin_cannot_decrypt_alice_credentials's analogous case above.
        with pytest.raises(TraitMethodError, match='suspended'):
            _ = me.sec_keys


def test_suspended_account_cannot_seed_new_machine(vault_env):  # noqa: F811
    """A suspended identity must not be able to re-establish local access on a *new* machine
    either -- `_user_init_new_machine` decrypts via `SecKeys.decrypt_private_key` directly, not
    `VaultUser.sec_keys_get()`, so it needs its own gate."""
    env = vault_env
    env.switch_os_user(ALICE)
    env.run_user_init(vault_login=ALICE, vault_pwd=ALICE_VAULT_PWD, master_pwd=ALICE_MASTER)

    env.switch_os_user(ADMIN)
    env.run_user_init(vault_login=ADMIN, vault_pwd=ADMIN_VAULT_PWD, master_pwd=ADMIN_MASTER)
    with Traitable.vault_store():
        me = VaultUser.existing_instance(user_id=ALICE)
        me.set_values(suspended=True).throw()
        me.save().throw()

    env.switch_os_user(ALICE)
    env.clear_local_keyring()
    rc = VaultUtils.user_init(
        new_machine=True,
        login=ALICE,
        password=ALICE_VAULT_PWD,
        master_password=ALICE_MASTER,
    )
    assert not rc
    assert 'suspended' in rc.error()
    assert (EnvVars.master_password_key, ALICE) not in env.keyring


def test_admin_save_user_credentials_refuses_suspended_account(vault_env):  # noqa: F811
    """A suspended account shouldn't be granted *new* resource access either."""
    env = vault_env
    env.switch_os_user(ADMIN)
    env.run_user_init(vault_login=ADMIN, vault_pwd=ADMIN_VAULT_PWD, master_pwd=ADMIN_MASTER)
    env.switch_os_user(ALICE)
    env.run_user_init(vault_login=ALICE, vault_pwd=ALICE_VAULT_PWD, master_pwd=ALICE_MASTER)

    env.switch_os_user(ADMIN)
    with Traitable.vault_store():
        me = VaultUser.existing_instance(user_id=ALICE)
        me.set_values(suspended=True).throw()
        me.save().throw()

    env.text_q.append(ALICE)  # 'Enter the vault login issued to this user:'
    rc = VaultUtils.admin_save_user_credentials()
    assert not rc
    assert 'suspended' in rc.error()


# ---------------------------------------------------------------------------
# --new-user / --new-machine
# ---------------------------------------------------------------------------


def test_new_machine_seeds_keyring_without_changing_vault_keys(vault_env):  # noqa: F811
    """After first-time registration, a wiped local keyring is restored via
    ``new_machine=True`` without rewriting the ``VaultUser`` key material."""
    env = vault_env
    env.switch_os_user(ALICE)
    env.run_user_init(vault_login=ALICE, vault_pwd=ALICE_VAULT_PWD, master_pwd=ALICE_MASTER)

    with Traitable.vault_store():
        me = VaultUser.existing_instance(user_id=ALICE)
        public_key = me.public_key
        private_key_encrypted = me.private_key_encrypted

    env.clear_local_keyring()
    assert not SecKeys.retrieve_master_password()[0]

    env.run_user_init(vault_login=ALICE, vault_pwd=ALICE_VAULT_PWD, master_pwd=ALICE_MASTER, new_machine=True)

    rc, mp = SecKeys.retrieve_master_password()
    assert rc and mp == ALICE_MASTER
    rc, login, pwd = SecKeys.retrieve_vault_login_password(VAULT_URI)
    assert rc and login == ALICE and pwd == ALICE_VAULT_PWD

    with Traitable.vault_store():
        me = VaultUser.existing_instance(user_id=ALICE)
        assert me.public_key == public_key
        assert me.private_key_encrypted == private_key_encrypted
        assert (
            me.sec_keys.decrypt_text(VaultResourceAccessor.retrieve_ra(CONCRETE_RESOURCE.TS_STORE, Resource.uri_no_dbname(VAULT_URI)).password)
            == ALICE_VAULT_PWD
        )


def test_new_machine_wrong_master_does_not_seed_keyring(vault_env):  # noqa: F811
    env = vault_env
    env.switch_os_user(ALICE)
    env.run_user_init(vault_login=ALICE, vault_pwd=ALICE_VAULT_PWD, master_pwd=ALICE_MASTER)
    env.clear_local_keyring()

    rc = VaultUtils.user_init(
        new_machine=True,
        login=ALICE,
        password=ALICE_VAULT_PWD,
        master_password='WrongMaster9!',
    )
    assert not rc
    assert 'does not unlock' in rc.error()

    # Neither keyring entry should have been written after a failed prove.
    assert (EnvVars.master_password_key, ALICE) not in env.keyring
    assert (VAULT_URI, ALICE) not in env.keyring


def test_new_machine_without_vault_user_points_to_new_user(vault_env):  # noqa: F811
    env = vault_env
    env.switch_os_user(ALICE)
    rc = VaultUtils.user_init(
        new_machine=True,
        login=ALICE,
        password=ALICE_VAULT_PWD,
        master_password=ALICE_MASTER,
    )
    assert not rc
    assert '--new-user' in rc.error()


def test_new_user_when_vault_user_exists_points_to_new_machine(vault_env):  # noqa: F811
    env = vault_env
    env.switch_os_user(ALICE)
    env.run_user_init(vault_login=ALICE, vault_pwd=ALICE_VAULT_PWD, master_pwd=ALICE_MASTER)
    env.clear_local_keyring()

    rc = VaultUtils.user_init(
        login=ALICE,
        password=ALICE_VAULT_PWD,
        master_password=ALICE_MASTER,
    )
    assert not rc
    assert '--new-machine' in rc.error()


# ---------------------------------------------------------------------------
# URI canonicalization tests — no vault required
# ---------------------------------------------------------------------------


class TestCanonicalUri:
    """``VaultResourceAccessor._canonical_uri`` normalises URIs before they
    are used as storage keys so that equivalent URIs (with / without default
    port, different capitalisation of the scheme, etc.) resolve to the same
    entry."""

    def test_adds_default_port_when_missing(self, vault_env):  # noqa: F811  (pytest fixture)
        """Port-free URI gains the resource's default port (27017 for duckdb /
        MongoDB) so it hashes to the same key as the explicit-port form."""
        no_port = VaultResourceAccessor._canonical_uri(CONCRETE_RESOURCE.TS_STORE, 'duckdb://vaulthost.example.com/_vault_')
        with_port = VaultResourceAccessor._canonical_uri(CONCRETE_RESOURCE.TS_STORE, 'duckdb://vaulthost.example.com:27017/_vault_')

        assert no_port == with_port
        assert ':27017' in no_port

    def test_explicit_port_unchanged(self):
        """An explicit non-default port is preserved as-is."""
        uri = VaultResourceAccessor._canonical_uri(CONCRETE_RESOURCE.TS_STORE, 'duckdb://vaulthost.example.com:9999/_vault_')
        assert ':9999' in uri
        assert ':27017' not in uri

    def test_netloc_preserved_through_uri_no_dbname(self):
        """``Resource.uri_no_dbname`` round-trips through the parser; ensures the port is
        carried through when the database name is stripped."""
        full_uri = 'duckdb://vaulthost.example.com:27017/_vault_'
        host_uri = Resource.uri_no_dbname(full_uri)

        assert host_uri == 'duckdb://vaulthost.example.com:27017'
        assert '/_vault_' not in host_uri

    def test_vault_uri_no_dbname_matches_canonical_host_uri(self, vault_env):  # noqa: F811  (pytest fixture)
        """The host URI produced by ``uri_no_dbname(VAULT_URI)`` is the same
        as what ``_canonical_uri`` produces for a port-free host URI, proving
        that self-registration and later retrieval resolve to the same key
        regardless of whether the caller includes the port."""
        stored_as = Resource.uri_no_dbname(VAULT_URI)  # what user_init stores
        looked_up = VaultResourceAccessor._canonical_uri(
            CONCRETE_RESOURCE.TS_STORE,
            'duckdb://vaulthost.example.com',  # caller omits port
        )
        assert stored_as == looked_up


class TestSaveAndRetrieveWithPortVariants:
    """``save_ra`` and ``retrieve_ra`` canonicalise the URI so that the same
    RA is found regardless of whether the caller includes the default port."""

    def test_save_portless_retrieve_portful(self, vault_env):  # noqa: F811  (pytest fixture)
        env = vault_env
        env.switch_os_user(ALICE)
        env.run_user_init(vault_login=ALICE, vault_pwd=ALICE_VAULT_PWD, master_pwd=ALICE_MASTER)

        portless = 'duckdb://otherhost.example.com/mydb'
        portful = 'duckdb://otherhost.example.com:27017/mydb'

        with Traitable.vault_store():
            VaultResourceAccessor.save_ra(
                resource_dt=CONCRETE_RESOURCE.TS_STORE,
                resource_uri=portless,  # stored after canonicalisation → adds :27017
                password=ALICE_VAULT_PWD,
                login=ALICE,
                username=ALICE,
            ).throw()

            # Retrieve with the explicit-port form — canonical match.
            ra = VaultResourceAccessor.retrieve_ra(CONCRETE_RESOURCE.TS_STORE, portful)
            assert ra.resource_uri == portful
            assert ra.login == ALICE

    def test_save_portful_retrieve_portless(self, vault_env):  # noqa: F811  (pytest fixture)
        env = vault_env
        env.switch_os_user(ALICE)
        env.run_user_init(vault_login=ALICE, vault_pwd=ALICE_VAULT_PWD, master_pwd=ALICE_MASTER)

        portless = 'duckdb://otherhost.example.com/mydb'
        portful = 'duckdb://otherhost.example.com:27017/mydb'

        with Traitable.vault_store():
            VaultResourceAccessor.save_ra(
                resource_dt=CONCRETE_RESOURCE.TS_STORE,
                resource_uri=portful,  # already canonical
                password=ALICE_VAULT_PWD,
                login=ALICE,
                username=ALICE,
            ).throw()

            # Retrieve with no port — canonicalised to :27017, same key.
            ra = VaultResourceAccessor.retrieve_ra(CONCRETE_RESOURCE.TS_STORE, portless)
            assert ra.resource_uri == portful  # retrieve_ra returns canonical URI
            assert ra.login == ALICE
