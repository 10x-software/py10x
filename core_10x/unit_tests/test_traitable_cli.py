import sys

import pytest
from core_10x.exec_control import CONVERT_VALUES_OFF
from core_10x.rc import RC, RC_TRUE
from core_10x.traitable import T
from core_10x.traitable_cli import TraitableCli

# ----------------------------------------------------------------------------
#   Test command hierarchy
# ----------------------------------------------------------------------------


class Cli(TraitableCli):
    """Master parser - the root command."""

    verbose: bool = T(False)


class Add(Cli, _command='add'):
    a: float = T(0.0)
    b: float = T(0.0)


class Greet(Cli, _command='greet'):
    name: str = T('world')


# ----------------------------------------------------------------------------
#   parse() - splitting argv into positional args and --option value pairs
# ----------------------------------------------------------------------------


def _parse(input_args):
    args, trait_values = [], {}
    rc = TraitableCli.parse(input_args, args, trait_values)
    return rc, args, trait_values


def test_parse_empty_args():
    rc, args, tv = _parse([])
    assert rc
    assert args == []
    assert tv == {}


def test_parse_positional_only():
    rc, args, tv = _parse(['add', 'sub'])
    assert rc
    assert args == ['add', 'sub']
    assert tv == {}


def test_parse_option_value_pairs():
    rc, args, tv = _parse(['--a', '2', '--b', '3'])
    assert rc
    assert args == []
    assert tv == {'a': '2', 'b': '3'}


def test_parse_dashes_become_underscores():
    # --some-option -> trait some_option
    rc, args, tv = _parse(['--dry-run', 'true', '--max-retries', '5'])
    assert rc
    assert args == []
    assert tv == {'dry_run': 'true', 'max_retries': '5'}


def test_parse_boolean_shortcut_true():
    # --flag (followed by another option) is equivalent to --flag true
    rc, args, tv = _parse(['--verbose', '--name', 'x'])
    assert rc
    assert args == []
    assert tv == {'verbose': 'true', 'name': 'x'}


def test_parse_boolean_shortcut_true_at_end():
    rc, _args, tv = _parse(['--verbose'])
    assert rc
    assert tv == {'verbose': 'true'}


def test_parse_boolean_shortcut_no_option():
    # --no-option is equivalent to --option false
    rc, _args, tv = _parse(['--no-verbose', '--no-dry-run'])
    assert rc
    assert tv == {'verbose': 'false', 'dry_run': 'false'}


def test_parse_positional_then_options():
    rc, args, tv = _parse(['add', '--a', '2', '--b', '3'])
    assert rc
    assert args == ['add']
    assert tv == {'a': '2', 'b': '3'}


def test_parse_negative_number_value():
    # a single-dash token is a value, not an option
    rc, _args, tv = _parse(['--a', '-3'])
    assert rc
    assert tv == {'a': '-3'}


# ----------------------------------------------------------------------------
#   parse() - error conditions
# ----------------------------------------------------------------------------


def test_parse_bare_double_dash():
    rc, _, _ = _parse(['--', 'value'])
    assert not rc
    assert 'Option name is missing' in rc.error()


# ----------------------------------------------------------------------------
#   instance_from_args() - routing to the right command class
# ----------------------------------------------------------------------------


def test_instantiate_master_no_subcommand():
    # instance_from_args() converts string tokens to trait types on its own.
    rc, obj = Cli.instance_from_args(['--verbose', 'true'])
    assert rc
    assert type(obj) is Cli
    assert obj.verbose is True


def test_instantiate_master_boolean_shortcut():
    # --verbose (no value) is equivalent to --verbose true
    rc, obj = Cli.instance_from_args(['--verbose'])
    assert rc
    assert type(obj) is Cli
    assert obj.verbose is True


def test_instantiate_master_no_boolean_shortcut():
    # --no-verbose is equivalent to --verbose false
    rc, obj = Cli.instance_from_args(['--no-verbose'])
    assert rc
    assert type(obj) is Cli
    assert obj.verbose is False


def test_instantiate_subcommand_add():
    rc, obj = Cli.instance_from_args(['add', '--a', '2', '--b', '3'])
    assert rc
    assert type(obj) is Add
    assert obj.a == 2.0
    assert obj.b == 3.0


def test_instantiate_subcommand_uses_defaults():
    rc, obj = Cli.instance_from_args(['greet'])
    assert rc
    assert type(obj) is Greet
    assert obj.name == 'world'


def test_instantiate_forces_conversion_inside_convert_off():
    # instance_from_args() turns value conversion on itself, overriding the surrounding context.
    with CONVERT_VALUES_OFF():
        rc, obj = Cli.instance_from_args(['add', '--a', '2', '--b', '3'])
    assert rc
    assert obj.a == 2.0
    assert obj.b == 3.0


# ----------------------------------------------------------------------------
#   instance_from_args() - error conditions
# ----------------------------------------------------------------------------


def test_instantiate_unknown_command():
    rc, obj = Cli.instance_from_args(['bogus'])
    assert not rc
    assert obj is None
    assert 'Unknown argument bogus' in rc.error()


def test_instantiate_unknown_attribute():
    rc, obj = Cli.instance_from_args(['--unknown', '1'])
    assert not rc
    assert obj is None
    assert 'unknown attribute unknown' in rc.error()


def test_instantiate_propagates_parse_error():
    rc, obj = Cli.instance_from_args(['--', 'oops'])
    assert not rc
    assert obj is None
    assert 'Option name is missing' in rc.error()


# ----------------------------------------------------------------------------
#   __init_subclass__ - command registration & validation
# ----------------------------------------------------------------------------


def test_subcommands_registered_on_master():
    assert Cli.s_switch['add'] is Add
    assert Cli.s_switch['greet'] is Greet


def test_master_may_not_have_command():
    with pytest.raises(AssertionError):

        class BadMaster(TraitableCli, _command='oops'):
            pass


def test_command_must_be_identifier():
    with pytest.raises(AssertionError):

        class BadCommand(Cli, _command='not an id'):
            pass


# ----------------------------------------------------------------------------
#   main() - console-script entry point
# ----------------------------------------------------------------------------


class MainCli(TraitableCli):
    """Usage: mycmd work"""


class Work(MainCli, _command='work'):
    fail: bool = T(False)

    def run(self):
        return RC(False, 'work failed') if self.fail else RC_TRUE


def test_main_returns_zero_on_success(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['mycmd', 'work'])
    assert MainCli.main() == 0


def test_main_returns_one_when_the_command_fails(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['mycmd', 'work', '--fail'])
    assert MainCli.main() == 1
    assert 'work failed' in capsys.readouterr().out


def test_main_returns_two_on_a_usage_error(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['mycmd', 'work', '--nope', 'x'])
    assert MainCli.main() == 2
    assert 'unknown attribute nope' in capsys.readouterr().out


def test_main_shows_usage_when_no_command_is_given(monkeypatch, capsys):
    """No positional word instantiates the *master*, which has no ``run`` — show its docstring.

    Regression: ``main`` used to call ``inst.run()`` unconditionally and died with
    ``AttributeError`` for any CLI whose master class defines no ``run`` of its own.
    """
    monkeypatch.setattr(sys, 'argv', ['mycmd'])
    assert MainCli.main() == 2
    assert 'Usage: mycmd work' in capsys.readouterr().out


class VerifyCli(TraitableCli):
    """Usage: vcli go"""

    blocked: bool = T(False)

    def post_verify(self):
        return RC(False, 'blocked by post_verify') if self.blocked else super().post_verify()


class Go(VerifyCli, _command='go'):
    def run(self):
        Go.ran = True
        return RC_TRUE


def test_main_calls_verify_before_run(monkeypatch, capsys):
    """``main`` calls ``verify()``, which includes ``post_verify`` — a failing hook skips ``run``."""
    Go.ran = False
    monkeypatch.setattr(sys, 'argv', ['vcli', 'go', '--blocked'])
    assert VerifyCli.main() == 1
    assert 'blocked by post_verify' in capsys.readouterr().out
    assert Go.ran is False

    monkeypatch.setattr(sys, 'argv', ['vcli', 'go'])
    assert VerifyCli.main() == 0
    assert Go.ran is True
