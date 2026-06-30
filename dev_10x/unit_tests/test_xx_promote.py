"""CLI routing tests for `dev_10x.xx_promote` (TraitableCli tree).

Pure helper tests live in test_xx_utils.py.
"""
from __future__ import annotations

import pytest

from dev_10x import xx_promote as xp


# ---------------------------------------------------------------- CLI routing (core_10x.traitable_cli)
@pytest.mark.parametrize("argv,cls,dry_run,push,publish", [
    (["pre"],                       "Pre",    False, False, False),
    (["pre", "--dry-run"],          "Pre",    True,  False, False),  # boolean --flag shortcut
    (["pre", "--dry-run", "true"],  "Pre",    True,  False, False),  # explicit value
    (["pre", "--publish"],          "Pre",    False, False, True),
    (["prod", "--push", "1"],       "Prod",   False, True,  False),
    (["prod", "--publish", "--push"], "Prod", False, True,  True),
    (["prod", "--no-dry-run"],      "Prod",   False, False, False),  # --no-flag shortcut
    (["status"],                    "Status", False, False, False),
])
def test_cli_routes_commands_and_flags(argv, cls, dry_run, push, publish):
    """Flags are real bools: CONVERT_VALUES_ON in XxPromote.instance_from_args coerces the strings."""
    rc, inst = xp.XxPromote.instance_from_args(argv)
    assert rc, "" if rc else rc.error()
    assert type(inst).__name__ == cls
    assert inst.dry_run == dry_run
    assert inst.push == push
    if hasattr(inst, "publish"):
        assert inst.publish == publish


def test_cli_yank_traits_and_unknown_command():
    rc, inst = xp.XxPromote.instance_from_args(["yank", "--pkg", "py10x-kernel", "--version", "0.2.0"])
    assert rc and type(inst).__name__ == "Yank"
    assert inst.get_value("pkg") == "py10x-kernel" and inst.get_value("version") == "0.2.0"
    rc, inst = xp.XxPromote.instance_from_args(["bogus"])
    assert not rc and inst is None
