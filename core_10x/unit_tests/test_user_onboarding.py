"""End-to-end test for the admin/user onboarding procedure documented in
``docs/USER_ONBOARDING_AUTH.md``.

The scenario, in order:

1. **Admin bootstrap.** A sysadmin pre-allocates a vault DB account for the
   admin (out of band). The admin then runs ``user_init`` on their own
   machine: master password lands in the OS keyring, ``VaultUser`` row lands
   in the vault, and a server-wide ``VaultResourceAccessor`` for the vault
   host is created. From now on ``Traitable.vault_store()`` works for the
   admin.

2. **Admin -> Alice.** Admin transmits Alice's vault login + temporary
   password to her, out of band.

3. **Alice self-registers.** Same flow as step 1, but for Alice.

4. **Alice -> Admin.** Alice tells the admin her OS user name (=
   ``VaultUser.user_id``). That is the *only* datum she has to send back.

5. **Admin -> vault.** Admin runs ``admin_save_user_credentials`` to add a
   ``VaultResourceAccessor`` for any *other* protected resource Alice needs
   (here: a relational DB on a different host).

6. **Alice connects.** ``VaultResourceAccessor.retrieve_ra`` resolves both
   the vault host (via the registration-time RA + ``uri_no_dbname`` fallback)
   and the relational DB (direct match), and Alice can decrypt the password
   in either case via her own master password.

The test exercises the **real** ``Traitable.vault_store`` /
``store_from_uri`` / ``VaultResourceAccessor`` code paths. The only mocked
boundaries are:

- the OS keyring (external state),
- ``input`` / ``getpass.getpass`` (interactive prompts),
- the OS user name (the C++ singleton ``OsUser.me`` is not mutable from
  Python), and
- a couple of one-line shims to plug ``DuckDbStore`` into the URI/protocol
  resolution that ``TsStore.spec_from_uri`` performs.
"""

from __future__ import annotations

import pytest

from core_10x.concrete_resource import CONCRETE_RESOURCE
from core_10x.resource import Resource
from core_10x.testlib.vault_env import vault_env
from core_10x.testlib.vault_env import VAULT_URI
from core_10x.trait_method_error import TraitMethodError
from core_10x.traitable import Traitable, VaultResourceAccessor, VaultUser
from core_10x.vault_utils import VaultUtils


# -- URIs and credentials specific to the user-onboarding scenario ---------
# (The ``vault_env`` fixture itself lives in ``core_10x.testlib.vault_env``
# and uses its own internal ``VAULT_URI`` matching the host below.)

VAULT_HOST_URI  = 'duckdb://vaulthost.example.com'              # no port number - should be added by round trip
MAIN_ON_VAULT   = 'duckdb://vaulthost.example.com:27017/main'   # different db, same host
PG_URI          = 'postgresql://pghost.example.com:5432/analytics'

ADMIN, ADMIN_VAULT_PWD, ADMIN_MASTER = 'admin', 'AdminVault7!', 'AdminMaster9!'
ALICE, ALICE_VAULT_PWD, ALICE_MASTER = 'alice', 'AliceVault7!', 'AliceMaster9!'
PG_PWD                               = 'PgWorker3!'


# -- The scenario ---------------------------------------------------------

def test_admin_user_onboarding_information_flow(vault_env): # noqa: F811  (pytest fixture)
    env = vault_env

    # ----------------------------------------------------------------- 0
    # Sysadmin (out of band) created vault DB accounts for the admin and
    # alice, with temporary passwords. We just declare them here; the
    # ``MongodbAdmin.update_user(...)`` call that produces them in
    # production is exercised by infra_10x tests.

    # ----------------------------------------------------------------- 1
    # ADMIN bootstraps themselves.
    env.switch_os_user(ADMIN)
    env.run_user_init(vault_login=ADMIN, vault_pwd=ADMIN_VAULT_PWD,
                      master_pwd=ADMIN_MASTER)

    # ----------------------------------------------------------------- 2
    # Admin transmits (vault_login=ALICE, vault_pwd=ALICE_VAULT_PWD) to
    # alice out of band.

    # ----------------------------------------------------------------- 3
    # ALICE self-registers.
    env.switch_os_user(ALICE)
    env.run_user_init(vault_login=ALICE, vault_pwd=ALICE_VAULT_PWD,
                      master_pwd=ALICE_MASTER)

    # Verify the bookkeeping that admin's step (5) will rely on:
    with Traitable.vault_store():
        me = VaultUser.existing_instance(user_id=ALICE)
        assert me.user_id == ALICE, \
            'VaultUser.user_id must equal the OS user name (the only datum ' \
            'alice has to communicate back to the admin in step 4)'
        assert me.public_key and me.private_key_encrypted

        # Server-wide RA created during self-registration: any other DB on
        # the same vault host is now reachable without a per-DB admin step.
        host_ra = VaultResourceAccessor.retrieve_ra(
            CONCRETE_RESOURCE.TS_STORE, VAULT_HOST_URI,
        )
        assert host_ra.login == ALICE
        assert me.sec_keys.decrypt_text(host_ra.password) == ALICE_VAULT_PWD

    # ----------------------------------------------------------------- 4
    # Alice tells admin her ``user_id`` — that is the only datum that
    # crosses back from user to admin.
    user_id_to_admin = ALICE

    # ----------------------------------------------------------------- 5
    # ADMIN runs ``admin_save_user_credentials`` for alice's relational DB.
    env.switch_os_user(ADMIN)
    rel_db_idx = CONCRETE_RESOURCE.all_names().index('REL_DB')
    env.text_q.extend([
        user_id_to_admin,   # 'Enter the user ID:'
        str(rel_db_idx),    # 'Choose CONCRETE_RESOURCE ...'
        PG_URI,             # 'Enter URI for REL_DB:'
        '',                 # 'Enter login name (alice):' -> default
    ])
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
            CONCRETE_RESOURCE.TS_STORE, MAIN_ON_VAULT,
        )
        assert ra.resource_uri == MAIN_ON_VAULT, \
            'returned RA reports the requested URI, not the registered one'
        assert ra.login == ALICE
        assert ra.user.sec_keys.decrypt_text(ra.password) == ALICE_VAULT_PWD

        # 6b) The relational DB, resolved against the admin-supplied RA.
        ra_pg = VaultResourceAccessor.retrieve_ra(
            CONCRETE_RESOURCE.REL_DB, PG_URI,
        )
        assert ra_pg.login == ALICE
        assert ra_pg.user.sec_keys.decrypt_text(ra_pg.password) == PG_PWD


def test_admin_cannot_decrypt_alice_credentials(vault_env): # noqa: F811  (pytest fixture)
    """Regression guard: even though the admin holds the vault open and can
    save resource passwords for alice (using only her public key), nothing
    in the admin's environment lets them recover plaintext credentials for
    other users."""

    env = vault_env

    # Bootstrap admin and alice as in the main test.
    env.switch_os_user(ADMIN)
    env.run_user_init(vault_login=ADMIN, vault_pwd=ADMIN_VAULT_PWD,
                      master_pwd=ADMIN_MASTER)
    env.switch_os_user(ALICE)
    env.run_user_init(vault_login=ALICE, vault_pwd=ALICE_VAULT_PWD,
                      master_pwd=ALICE_MASTER)

    # Admin saves an RA for alice's REL_DB (using only her public key).
    env.switch_os_user(ADMIN)
    with Traitable.vault_store():
        VaultResourceAccessor.save_ra(
            resource_dt     = CONCRETE_RESOURCE.REL_DB,
            resource_uri    = PG_URI,
            password        = PG_PWD,
            login           = ALICE,
            username        = ALICE,
        ).throw()

        # Trying to decrypt as the admin must fail — the vault has alice's
        # *encrypted* private key, but only alice's master password (kept
        # in alice's OS keyring) can unlock it.
        ra = VaultResourceAccessor.retrieve_ra(
            CONCRETE_RESOURCE.REL_DB, PG_URI, username=ALICE,
        )
        with pytest.raises(TraitMethodError):
            ra.user.sec_keys.decrypt_text(ra.password)

    # Alice can decrypt on her own machine.
    env.switch_os_user(ALICE)
    with Traitable.vault_store():
        ra = VaultResourceAccessor.retrieve_ra(
            CONCRETE_RESOURCE.REL_DB, PG_URI, username=ALICE,
        )
        assert ra.user.sec_keys.decrypt_text(ra.password) == PG_PWD


# ---------------------------------------------------------------------------
# URI canonicalization tests — no vault required
# ---------------------------------------------------------------------------

class TestCanonicalUri:
    """``VaultResourceAccessor._canonical_uri`` normalises URIs before they
    are used as storage keys so that equivalent URIs (with / without default
    port, different capitalisation of the scheme, etc.) resolve to the same
    entry."""

    def test_adds_default_port_when_missing(self,vault_env): # noqa: F811  (pytest fixture)
        """Port-free URI gains the resource's default port (27017 for duckdb /
        MongoDB) so it hashes to the same key as the explicit-port form."""
        no_port   = VaultResourceAccessor._canonical_uri(
            CONCRETE_RESOURCE.TS_STORE, 'duckdb://vaulthost.example.com/_vault_')
        with_port = VaultResourceAccessor._canonical_uri(
            CONCRETE_RESOURCE.TS_STORE, 'duckdb://vaulthost.example.com:27017/_vault_')

        assert no_port == with_port
        assert ':27017' in no_port

    def test_explicit_port_unchanged(self):
        """An explicit non-default port is preserved as-is."""
        uri = VaultResourceAccessor._canonical_uri(
            CONCRETE_RESOURCE.TS_STORE, 'duckdb://vaulthost.example.com:9999/_vault_')
        assert ':9999' in uri
        assert ':27017' not in uri

    def test_netloc_preserved_through_uri_no_dbname(self):
        """``Resource.uri_no_dbname`` round-trips through the parser; ensures the port is
        carried through when the database name is stripped."""
        full_uri = 'duckdb://vaulthost.example.com:27017/_vault_'
        host_uri = Resource.uri_no_dbname(full_uri)

        assert host_uri == 'duckdb://vaulthost.example.com:27017'
        assert '/_vault_' not in host_uri

    def test_vault_uri_no_dbname_matches_canonical_host_uri(self, vault_env): # noqa: F811  (pytest fixture)
        """The host URI produced by ``uri_no_dbname(VAULT_URI)`` is the same
        as what ``_canonical_uri`` produces for a port-free host URI, proving
        that self-registration and later retrieval resolve to the same key
        regardless of whether the caller includes the port."""
        stored_as = Resource.uri_no_dbname(VAULT_URI)   # what user_init stores
        looked_up = VaultResourceAccessor._canonical_uri(
            CONCRETE_RESOURCE.TS_STORE,
            'duckdb://vaulthost.example.com',           # caller omits port
        )
        assert stored_as == looked_up


class TestSaveAndRetrieveWithPortVariants:
    """``save_ra`` and ``retrieve_ra`` canonicalise the URI so that the same
    RA is found regardless of whether the caller includes the default port."""

    def test_save_portless_retrieve_portful(self, vault_env): # noqa: F811  (pytest fixture)
        env = vault_env
        env.switch_os_user(ALICE)
        env.run_user_init(vault_login=ALICE, vault_pwd=ALICE_VAULT_PWD,
                          master_pwd=ALICE_MASTER)

        portless = 'duckdb://otherhost.example.com/mydb'
        portful  = 'duckdb://otherhost.example.com:27017/mydb'

        with Traitable.vault_store():
            VaultResourceAccessor.save_ra(
                resource_dt  = CONCRETE_RESOURCE.TS_STORE,
                resource_uri = portless,       # stored after canonicalisation → adds :27017
                password     = ALICE_VAULT_PWD,
                login        = ALICE,
                username     = ALICE,
            ).throw()

            # Retrieve with the explicit-port form — canonical match.
            ra = VaultResourceAccessor.retrieve_ra(
                CONCRETE_RESOURCE.TS_STORE, portful)
            assert ra.resource_uri == portful
            assert ra.login == ALICE

    def test_save_portful_retrieve_portless(self, vault_env): # noqa: F811  (pytest fixture)
        env = vault_env
        env.switch_os_user(ALICE)
        env.run_user_init(vault_login=ALICE, vault_pwd=ALICE_VAULT_PWD,
                          master_pwd=ALICE_MASTER)

        portless = 'duckdb://otherhost.example.com/mydb'
        portful  = 'duckdb://otherhost.example.com:27017/mydb'

        with Traitable.vault_store():
            VaultResourceAccessor.save_ra(
                resource_dt  = CONCRETE_RESOURCE.TS_STORE,
                resource_uri = portful,        # already canonical
                password     = ALICE_VAULT_PWD,
                login        = ALICE,
                username     = ALICE,
            ).throw()

            # Retrieve with no port — canonicalised to :27017, same key.
            ra = VaultResourceAccessor.retrieve_ra(
                CONCRETE_RESOURCE.TS_STORE, portless)
            assert ra.resource_uri == portful   # retrieve_ra returns canonical URI
            assert ra.login == ALICE
