"""CLI routing for ``xx-user-init`` (``UserInitCli``). Vault I/O is mocked."""

from __future__ import annotations

import sys

from core_10x.apps.user_init import UserInitCli
from core_10x.rc import RC_TRUE


def _run(monkeypatch, argv, user_init):
    monkeypatch.setattr(sys, 'argv', argv)
    monkeypatch.setattr('core_10x.vault_utils.VaultUtils.user_init', user_init)
    return UserInitCli.main()


def test_default_is_new_user(monkeypatch):
    seen = {}

    def user_init(*, new_machine, **_kwargs):
        seen['new_machine'] = new_machine
        return RC_TRUE

    assert _run(monkeypatch, ['xx-user-init'], user_init) == 0
    assert seen['new_machine'] is False


def test_new_user_flag(monkeypatch):
    seen = {}

    def user_init(*, new_machine, **_kwargs):
        seen['new_machine'] = new_machine
        return RC_TRUE

    assert _run(monkeypatch, ['xx-user-init', '--new-user'], user_init) == 0
    assert seen['new_machine'] is False


def test_new_machine_flag(monkeypatch):
    seen = {}

    def user_init(*, new_machine, **_kwargs):
        seen['new_machine'] = new_machine
        return RC_TRUE

    assert _run(monkeypatch, ['xx-user-init', '--new-machine'], user_init) == 0
    assert seen['new_machine'] is True


def test_both_flags_are_rejected(monkeypatch, capsys):
    def user_init(**_kwargs):
        raise AssertionError('VaultUtils.user_init must not run when both flags are set')

    assert _run(monkeypatch, ['xx-user-init', '--new-user', '--new-machine'], user_init) == 1
    assert 'only one of --new-user or --new-machine' in capsys.readouterr().out
