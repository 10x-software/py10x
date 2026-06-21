"""Reusable ``vault_env`` pytest fixture for tests that exercise the real
``Traitable.vault_store`` / ``store_from_uri`` / ``VaultResourceAccessor``
code paths.

The fixture plumbs the bare minimum so the production flows can run
end-to-end inside a single test process:

- in-memory keyring (``sec_keys.keyring`` patched);
- queues for ``input`` / ``getpass.getpass`` (interactive prompts);
- a switchable OS user name (``OsUser.me`` is a C++ singleton, so we swap
  the binding seen by ``sec_keys`` and ``traitable``);
- ``TestStore.s_with_auth`` flipped to True so vault-aware codepaths run;
- ``TestStore.new_instance`` short-circuited to a single shared instance
  (so admin and alice see the same vault deployment).

URI parsing, ``is_running_with_auth``, and the ``testdb://`` protocol
registration all live in ``infra_10x/duckdb_store.py`` itself; the
fixture only flips the auth flag and the ``new_instance`` factory.

The fixture is **not** auto-collected: tests that need it should write::

    from core_10x.testlib.vault_env import vault_env  # noqa: F401  (pytest fixture)

The unused-import suppression is the standard idiom for fixture re-export.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from py10x_kernel import BTraitableProcessor, XCache

import core_10x.sec_keys as sec_keys_mod
import core_10x.traitable as traitable_mod
import core_10x.vault_utils as vault_utils_mod
from core_10x.environment_variables import EnvVars
from core_10x.resource import Resource
from core_10x.sec_keys import SecKeys
from infra_10x.duckdb_store import DuckDbStore as _TestStore
from core_10x.traitable import Traitable, VaultUser
from core_10x.ts_store import TsStore
from core_10x.vault_utils import VaultUtils


# Default vault URI used by ``vault_env``.  Tests may save resource accessors
# for any other ``testdb://`` URI; this one is what ``EnvVars.main_vault_uri``
# points to so ``Traitable.vault_store()`` resolves.
VAULT_URI = 'testdb://vaulthost.example.com:27017/_vault_'


def _clear_internal_state():
    """Drop process-wide cached state earlier tests may have populated.

    The sequence matters: ``end_using()`` releases the current
    ``BTraitableProcessor`` only *after* ``XCache.clear()`` so any references
    held by the cache are gone — otherwise the prime-table backing the
    B-traitable class registry keeps growing across tests and eventually
    overflows.
    """
    SecKeys.retrieve_master_password.__func__.clear()
    SecKeys.retrieve_vault_login_password.__func__.clear()
    SecKeys.check_vault_uri.__func__.clear()
    Traitable.__dict__['vault_store'].__func__.clear()
    TsStore.s_instances.clear()
    XCache.clear()
    BTraitableProcessor.current().end_using()


@pytest.fixture
def vault_env(monkeypatch):
    keyring     = {}
    current_os  = ['']
    text_q      = []
    secret_q    = []
    vault_db    = _TestStore()

    # 1. Keyring (in-memory).
    monkeypatch.setattr(sec_keys_mod.keyring, 'get_password',
                        lambda s, u:    keyring.get((s, u)))
    monkeypatch.setattr(sec_keys_mod.keyring, 'set_password',
                        lambda s, u, p: keyring.__setitem__((s, u), p))
    monkeypatch.setattr(sec_keys_mod.keyring, 'delete_password',
                        lambda s, u:    keyring.pop((s, u), None))

    # 2. OS user — used by SecKeys (master password / vault keyring lookups)
    #    and as the default for ``VaultUser.user_id``.
    fake_os = SimpleNamespace(me=SimpleNamespace(name=lambda: current_os[0]))
    monkeypatch.setattr(sec_keys_mod, 'OsUser', fake_os)
    monkeypatch.setattr(traitable_mod, 'OsUser', fake_os)
    # ``VaultUser.myname`` is @cache'd at the class level; replace with a
    # fresh classmethod that always re-reads ``current_os``.
    monkeypatch.setattr(VaultUser, 'myname',
                        classmethod(lambda cls: current_os[0]))

    # 3. Prompts. ``vault_utils`` imports the ``getpass`` *module*, so patch
    #    its bound attribute as well as the global one.
    monkeypatch.setattr('builtins.input',  lambda *_a, **_k: text_q.pop(0))
    monkeypatch.setattr('getpass.getpass', lambda *_a, **_k: secret_q.pop(0))
    monkeypatch.setattr(vault_utils_mod.getpass, 'getpass',
                                           lambda *_a, **_k: secret_q.pop(0))

    # 4. Auth-required + every ``_TestStore.instance(...)`` returns the same
    #    store; admin and alice's connections share the underlying
    #    "deployment" so they can read/write each other's state.
    monkeypatch.setattr(_TestStore, 's_with_auth', True)
    monkeypatch.setattr(_TestStore, 's_instance_kwargs_map',  _TestStore.s_instance_kwargs_map|{
        Resource.PORT_TAG: (Resource.PORT_TAG, 27017),
    })
    monkeypatch.setattr(_TestStore, 'new_instance',
                        classmethod(lambda cls, *a, **kw: vault_db))

    # 5. Vault URI (direct env-var assignment, the same idiom as
    #    ``ui_10x/apps/collection_editor_app.py``).
    monkeypatch.setattr(EnvVars, 'main_vault_uri', VAULT_URI)

    # 6. Drop any process-wide cached state that earlier tests / module
    #    imports may have populated.
    _clear_internal_state()

    env = SimpleNamespace(
        keyring     = keyring,
        text_q      = text_q,
        secret_q    = secret_q,
        vault_db    = vault_db,
        as_os_user  = current_os,  # mutate ``[0]`` to switch user
    )

    def switch_os_user(name: str) -> None:
        """Change the OS user that ``SecKeys`` / ``VaultUser.myname`` see.

        ``SecKeys.retrieve_*`` and ``Traitable.vault_store`` are ``@cache``'d
        process-globally; in production each user runs in their own process
        so they never observe stale entries belonging to another user — for
        the test we have to invalidate them by hand.  ``XCache`` is the
        framework-wide Traitable cache: clearing it forces
        ``existing_instance`` to reload from the underlying store, which is
        what we want when switching identity.
        """
        current_os[0] = name
        _clear_internal_state()

    def run_user_init(*, vault_login: str, vault_pwd: str, master_pwd: str) -> None:
        """Feed canned answers to ``VaultUtils.user_init()``'s prompts."""
        text_q.append(vault_login)
        secret_q.extend([vault_pwd, master_pwd, master_pwd])
        VaultUtils.user_init().throw()
        assert not text_q and not secret_q, 'queued prompts left over'

        _clear_internal_state()

    env.switch_os_user = switch_os_user
    env.run_user_init  = run_user_init

    yield env

    _clear_internal_state()
