"""In-memory-only ``keyring`` backend for unattended functional (service) accounts.

``core_10x.sec_keys.SecKeys`` reads/writes secrets through the ``keyring`` package, which on a
desktop resolves to an OS credential store (macOS Keychain, Windows Credential Manager, or a
Linux Secret Service session). A headless functional-account container has none of those, and
none of ``keyring``'s bundled ``keyrings.alt`` fallbacks are appropriate either: they can
silently auto-select onto ``PlaintextKeyring`` (secrets written to disk unencrypted) via
priority-based backend discovery, and the alternative ``EncryptedKeyring`` needs an interactive
passphrase, which defeats unattended use anyway.

This backend instead holds secrets purely in memory, loaded once (at first use) from a JSON
manifest file at a fixed, agreed-upon location -- the path a container orchestrator (e.g.
Kubernetes, via a Secret mounted on a tmpfs volume) is expected to have already populated. It
never writes anything back to disk itself -- the mounted file (backed by the platform's secret
store) remains the durable record.

Wiring: set the ``PYTHON_KEYRING_BACKEND`` environment variable to
``core_10x.functional_account_keyring.FunctionalAccountKeyring`` and
``XX_FUNCTIONAL_ACCOUNT_SECRETS_FILE`` to the manifest path (``docker/entrypoint.sh`` does both).
``keyring`` checks ``PYTHON_KEYRING_BACKEND`` itself, before any config file or priority-based
discovery (see ``keyring.core.load_env``), and constructs the backend with no arguments the
first time anything calls ``keyring.get_password``/``set_password`` -- so this works correctly
regardless of which process ends up making that call, with no explicit "install" step needed.
(An explicit, eager install -- e.g. from a wrapper process that then ``exec``s the real
workload -- does NOT work: ``exec`` replaces the process image, discarding all interpreter
state including any previously-installed backend. Only environment variables and the
filesystem survive that boundary, which is exactly what this mechanism relies on.)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import keyring
import keyring.backend
import keyring.errors

SECRETS_FILE_ENV_VAR = 'XX_FUNCTIONAL_ACCOUNT_SECRETS_FILE'


class FunctionalAccountKeyring(keyring.backend.KeyringBackend):
    """In-memory-only backend: serves ``(service, username) -> password`` from a dict.

    Never persists anything to disk. Constructible two ways:

    - no-arg (what ``PYTHON_KEYRING_BACKEND`` auto-discovery uses): reads the manifest path
      from the ``XX_FUNCTIONAL_ACCOUNT_SECRETS_FILE`` env var;
    - :meth:`from_secrets_file` (what tests use, for explicit control): reads an arbitrary
      given path, independent of the environment.

    ``priority`` is irrelevant here beyond satisfying the abstract base class contract -- this
    backend is only ever selected explicitly via ``PYTHON_KEYRING_BACKEND`` or
    ``keyring.set_keyring(...)``, never through priority-based auto-discovery (that's exactly
    the ``keyrings.alt`` footgun this avoids).
    """

    priority = -1

    def __init__(self, entries: dict[tuple[str, str], str] | None = None):
        super().__init__()
        if entries is None:
            secrets_file = os.environ.get(SECRETS_FILE_ENV_VAR)
            if not secrets_file:
                raise RuntimeError(
                    f'{SECRETS_FILE_ENV_VAR} is not set (required for {type(self).__name__} '
                    'when constructed with no arguments, e.g. via PYTHON_KEYRING_BACKEND auto-discovery)'
                )
            entries = self._read_manifest(secrets_file)
        self._entries: dict[tuple[str, str], str] = dict(entries)

    @staticmethod
    def _read_manifest(secrets_file: str | Path) -> dict[tuple[str, str], str]:
        """Parse a JSON manifest: ``[{"service", "username", "password"}, ...]``.

        Shaped exactly like what ``SecKeys.change_master_password`` /
        ``change_vault_login_password`` would have written, so a provisioning script can
        produce the manifest directly from the same values.
        """
        records = json.loads(Path(secrets_file).read_text())
        return {(r['service'], r['username']): r['password'] for r in records}

    @classmethod
    def from_secrets_file(cls, secrets_file: str | Path) -> FunctionalAccountKeyring:
        """Build a backend from an explicit manifest path, independent of the environment."""
        return cls(entries=cls._read_manifest(secrets_file))

    def get_password(self, service: str, username: str) -> str | None:
        return self._entries.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._entries[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        try:
            del self._entries[(service, username)]
        except KeyError:
            raise keyring.errors.PasswordDeleteError(f'{service!r}/{username!r} not found') from None
