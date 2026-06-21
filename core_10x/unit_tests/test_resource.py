"""Unit tests for ``core_10x.resource`` and ``NamedResource``.

Two flavors of test live here:

* Static (no fixtures): ``NamedResource`` declaration and integrity rules.
* Behavioral (uses the ``vault_env`` fixture from
  ``core_10x.testlib.vault_env``): ``NamedResource.resource_instance()``
  round-trips through the vault.
"""

from __future__ import annotations

import pytest

from core_10x.concrete_resource import CONCRETE_RESOURCE
from core_10x.exec_control import CACHE_ONLY
from infra_10x.duckdb_store import DuckDbStore as _TestStore
from core_10x.testlib.vault_env import vault_env
from core_10x.traitable import (
    NamedResource,
    NamedTsStore,
    Traitable,
    VaultResourceAccessor,
)


# Credentials/URIs for the resource-instance scenario.  Distinct from the
# ones in ``test_user_onboarding`` so the two test files cannot interfere
# with each other through cached lookups.
ALICE, ALICE_VAULT_PWD, ALICE_MASTER = 'alice_res', 'AliceRes7!', 'AliceMaster9!'

# A vault-host URI (matches the ``VAULT_URI`` host in conftest).
VAULT_HOST_URI    = 'testdb://vaulthost.example.com:27017'
ANOTHER_DB_URI    = 'testdb://vaulthost.example.com/another'   # has matching RA in vault-hit test
NO_RA_URI         = 'testdb://otherhost.example.com/lonely'    # has no RA in vault-miss test
RESOURCE_PWD      = 'ResourcePwd9!'


# ---------------------------------------------------------------------------
# Static integrity tests (no fixture)
# ---------------------------------------------------------------------------


class TestNamedResourceIntegrity:
    """``NamedResource`` is the canonical resource family in the framework:
    members must declare ``s_resource_dt``.  ``check_integrity`` enforces it
    at class-definition time, so the failure mode is a clear ``RuntimeError``
    raised during the offending ``class`` statement."""

    def test_named_ts_store_is_a_resource_family_member(self):
        """The shipped ``NamedTsStore`` declares ``s_resource_dt`` and ends up
        as a member of the ``NamedResource`` family (sharing its collection)."""
        assert NamedResource.is_bundle_base()
        assert not NamedTsStore.is_bundle_base()
        assert NamedTsStore.s_bundle_base is NamedResource
        assert NamedTsStore.s_resource_dt is CONCRETE_RESOURCE.TS_STORE
        # Members share the family collection (one DB collection per family).
        assert NamedTsStore.collection == NamedResource.collection

    def test_member_without_s_resource_dt_is_rejected(self):
        """A member that forgets to set ``s_resource_dt`` must fail
        ``NamedResource.check_integrity`` at class-creation time."""
        with pytest.raises(RuntimeError, match='Must define s_resource_dt'):

            class _BrokenResource(NamedResource):
                pass  # no s_resource_dt -> fails check_integrity

    def test_member_with_explicit_s_resource_dt_is_accepted(self):
        """A member that does define ``s_resource_dt`` is registered on
        ``NamedResource`` and inherits the standard NamedResource trait set."""

        class _OkResource(NamedResource):
            s_resource_dt: CONCRETE_RESOURCE = CONCRETE_RESOURCE.REL_DB

        assert _OkResource.s_bundle_base is NamedResource
        assert _OkResource.s_resource_dt is CONCRETE_RESOURCE.REL_DB
        # Inherited trait set from NamedResource: logical_name (ID) and uri.
        assert 'logical_name' in _OkResource.s_dir
        assert 'uri' in _OkResource.s_dir


# ---------------------------------------------------------------------------
# Behavioral tests for resource_instance() (uses vault_env fixture)
# ---------------------------------------------------------------------------


class TestNamedResourceInstance:
    """``NamedResource.resource_instance()`` has two branches:

    * vault-hit: ``VaultResourceAccessor.retrieve_ra(s_resource_dt, uri)``
      returns an RA, and the resource is built from the RA's stored
      credentials (``ra.resource``);
    * vault-miss: ``retrieve_ra`` raises ``ValueError`` and the resource
      is built directly from the URI (``s_resource_dt.value.instance_from_uri(uri)``).

    Both branches must return a working ``_TestStore`` here.  We spy on
    ``_TestStore.new_instance`` to confirm which branch ran by inspecting
    whether credentials were forwarded.
    """

    def _spy_new_instance(self, vault_env, monkeypatch): # noqa: F811  (pytest fixture)
        """Replace ``_TestStore.new_instance`` with a spy that records each
        call's kwargs and still returns ``vault_env.vault_db`` (matching the
        fixture-level mock)."""
        calls = []
        vault_db = vault_env.vault_db

        def _spy(cls, *args, **kwargs):
            calls.append({'args': args, 'kwargs': dict(kwargs)})
            return vault_db

        monkeypatch.setattr(_TestStore, 'new_instance', classmethod(_spy))
        return calls

    def _bootstrap_alice(self, env):
        """Self-register ALICE via ``user_init`` so the vault store is
        unlocked and her ``VaultUser`` row exists."""
        env.switch_os_user(ALICE)
        env.run_user_init(
            vault_login=ALICE, vault_pwd=ALICE_VAULT_PWD,
            master_pwd=ALICE_MASTER,
        )

    def _last_call_for_host(self, calls, hostname):
        """Return the most recent recorded ``new_instance`` call for the
        given hostname (multiple unrelated calls happen during
        ``vault_store()`` setup)."""
        matches = [c for c in calls if c['kwargs'].get('hostname') == hostname]
        assert matches, f'no _TestStore.new_instance call for host {hostname}; got {calls!r}'
        return matches[-1]

    def test_vault_hit_uses_credentials_from_vault(self, vault_env, monkeypatch): # noqa: F811  (pytest fixture)
        """When an RA exists for ``(s_resource_dt, uri)``, ``resource_instance``
        forwards the RA's credentials to ``instance_from_uri``."""
        env = vault_env
        self._bootstrap_alice(env)

        with Traitable.vault_store():
            VaultResourceAccessor.save_ra(
                resource_dt   = CONCRETE_RESOURCE.TS_STORE,
                resource_uri  = ANOTHER_DB_URI,
                password      = RESOURCE_PWD,
                login         = ALICE,
                username      = ALICE,
            ).throw()

        calls = self._spy_new_instance(env, monkeypatch)

        with CACHE_ONLY():
            nts = NamedTsStore(logical_name='alice_db')
            nts.uri = ANOTHER_DB_URI
        store = nts.resource_instance()

        assert store is env.vault_db
        # Vault-hit branch forwards the credentials retrieved from the RA
        # (decrypted by the user's master password) to ``instance_from_uri``.
        kwargs = self._last_call_for_host(calls, 'vaulthost.example.com')['kwargs']
        # The ``ANOTHER_DB_URI`` dbname distinguishes this from the
        # vault-store ``new_instance`` call (whose dbname is ``_vault_``).
        assert kwargs.get('dbname') == 'another'
        assert kwargs.get('username') == ALICE
        assert kwargs.get('password') == RESOURCE_PWD

    def test_vault_miss_falls_back_to_instance_from_uri(self, vault_env, monkeypatch): # noqa: F811  (pytest fixture)
        """When no RA exists for ``(s_resource_dt, uri)``, ``retrieve_ra`` raises
        and ``resource_instance`` falls back to a credential-less
        ``instance_from_uri`` call."""
        env = vault_env
        self._bootstrap_alice(env)

        # No save_ra() for NO_RA_URI - ``retrieve_ra`` will raise ValueError.
        calls = self._spy_new_instance(env, monkeypatch)

        with CACHE_ONLY():
            nts = NamedTsStore(logical_name='lonely_db')
            nts.uri = NO_RA_URI
        store = nts.resource_instance()

        assert store is env.vault_db
        # Fallback branch: ``instance_from_uri(self.uri)`` does not pass
        # credentials.  Confirm by inspecting the call for the resource's
        # host (distinct from the vault host).
        kwargs = self._last_call_for_host(calls, 'otherhost.example.com')['kwargs']
        assert kwargs.get('dbname') == 'lonely'
        assert not kwargs.get('username')
        assert not kwargs.get('password')
