"""GitHub login case must match Mongo keyring names. No network and no prompts."""

from __future__ import annotations

import pytest
from infra_10x import mongodb_utils as mu

_CACHE_CLEARS = (mu.git_user.clear, mu.all_git_users.clear, mu.git_token.clear)


class _Json:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _Vault:
    def __init__(self):
        self.passwords: dict[tuple[str, str], str] = {}
        self.lookups: list[tuple[str, str]] = []
        self.deleted: list[tuple[str, str]] = []
        self.saved: list[tuple[str, str]] = []

    def get_password(self, service, username):
        self.lookups.append((service, username))
        return self.passwords.get((service, username))

    def set_password(self, service, username, password):
        self.saved.append((service, username))
        self.passwords[(service, username)] = password

    def delete_password(self, service, username):
        self.deleted.append((service, username))
        self.passwords.pop((service, username), None)


class _Admin:
    """Records every drop request, including the connected user the real admin would refuse."""

    def __init__(self, hostname, username, password, port=27017):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port
        self.deleted: list[str] = []

    def delete_user(self, username):
        self.deleted.append(username)


def _recording_admin(created):
    class RecordingAdmin(_Admin):
        def __init__(self, hostname, username, password, port=27017):
            super().__init__(hostname, username, password, port=port)
            created.append(self)

    return RecordingAdmin


def _refuse_input(prompt=''):
    pytest.fail(f'input() prompted: {prompt}')


def _prompted_password(prompt=''):
    return 'PROMPTED'


@pytest.fixture
def git_keyring(monkeypatch):
    for clear in _CACHE_CLEARS:
        clear()

    def fake_get(url, headers=None, **kwargs):
        assert headers == {'Authorization': 'token tok'}
        if url == 'https://api.github.com/orgs/acme/members':
            return _Json([{'id': 42, 'login': 'Alice'}])
        if url in ('https://api.github.com/user', 'https://api.github.com/user/42'):
            return _Json({'login': 'Alice', 'name': 'Alice Smith', 'id': 42})
        pytest.fail(f'unexpected URL: {url}')

    def fake_remote(*args, **kwargs):
        return 'https://github.com/acme/py10x.git'

    def fail_getoutput(cmd):
        pytest.fail(f'git credential invoked: {cmd}')

    vault = _Vault()
    monkeypatch.setattr(mu, 'git_token', lambda: 'tok')
    monkeypatch.setattr(mu.requests, 'get', fake_get)
    monkeypatch.setattr(mu.subprocess, 'check_output', fake_remote)
    monkeypatch.setattr(mu.subprocess, 'getoutput', fail_getoutput)
    monkeypatch.setattr('builtins.input', _refuse_input)
    monkeypatch.setattr(mu, 'getpass', _prompted_password)
    monkeypatch.setattr(mu.keyring, 'get_password', vault.get_password)
    monkeypatch.setattr(mu.keyring, 'set_password', vault.set_password)
    monkeypatch.setattr(mu.keyring, 'delete_password', vault.delete_password)
    yield vault
    for clear in _CACHE_CLEARS:
        clear()


def test_mixed_case_github_login_uses_one_keyring_name(git_keyring, monkeypatch):
    """login 'Alice', name 'Alice Smith' → keyring user 'alice', and that xxadmin key stays."""
    vault = git_keyring
    vault.passwords[('xxuser', 'alice')] = 'user-secret'
    vault.passwords[('xxadmin', 'alice-admin')] = 'admin-secret'

    assert mu.all_git_users() == ['alice']
    assert mu.get_credentials('xxuser', 'mongo.example') == {'username': 'alice', 'password': 'user-secret'}
    assert vault.lookups == [('xxuser', 'alice')]
    assert mu.get_credentials('xxadmin', 'mongo.example') == {'username': 'alice-admin', 'password': 'admin-secret'}
    assert vault.saved == []

    mu.clear_vault()
    assert ('xxadmin', 'alice-admin') not in vault.deleted
    assert vault.passwords[('xxadmin', 'alice-admin')] == 'admin-secret'

    created = []
    monkeypatch.setattr(mu, 'MongodbAdmin', _recording_admin(created))
    mu.drop_users('mongo.example')
    assert created[0].username == 'alice-admin'
    assert created[0].deleted == ['alice']


def test_get_credentials_falls_back_to_lowercased_display_name(git_keyring, monkeypatch):
    vault = git_keyring
    vault.passwords[('xxuser', 'alice smith')] = 'legacy-user'
    vault.passwords[('xxadmin', 'alice smith-admin')] = 'legacy-admin'

    assert mu.get_credentials('xxuser', 'mongo.example') == {'username': 'alice smith', 'password': 'legacy-user'}
    assert mu.get_credentials('xxadmin', 'mongo.example') == {'username': 'alice smith-admin', 'password': 'legacy-admin'}
    assert vault.lookups == [
        ('xxuser', 'alice'),
        ('xxuser', 'alice smith'),
        ('xxadmin', 'alice-admin'),
        ('xxadmin', 'alice smith-admin'),
    ]
    assert vault.saved == []

    created = []
    monkeypatch.setattr(mu, 'MongodbAdmin', _recording_admin(created))
    mu.drop_users('mongo.example')
    assert created[0].username == 'alice smith-admin'
    assert created[0].deleted == ['alice']
